import io
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_docpilot.db")

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import MedicalRecord, OcrResult, ProcessingJob
from ocr_worker.engines import EngineLine, EnginePage, OcrError
from ocr_worker.engines.pdftext import PdfTextEngine
from ocr_worker.run import Worker

HEADERS = {"X-User-Role": "patient"}
DOCTOR = {"X-User-Role": "doctor"}


# --- fake engines (deterministic, no model downloads) ----------------------

class FakeEngine:
    name = "fake"
    model = "fake-1"

    def __init__(self, confidence=0.95, fail_pages=(), raise_error=None):
        self.confidence = confidence
        self.fail_pages = set(fail_pages)
        self.raise_error = raise_error
        self.calls = []

    def warmup(self):
        return None

    def ocr_image(self, image_path, page_number):
        self.calls.append(page_number)
        if self.raise_error:
            raise self.raise_error
        if page_number in self.fail_pages:
            raise OcrError("ocr_failure", f"engine choked on page {page_number}", retryable=True)
        return EnginePage(page_number=page_number, lines=[
            EngineLine(text=f"Metformin 500 mg (page {page_number})", confidence=self.confidence),
        ])


# --- fixtures ---------------------------------------------------------------

def png_bytes(size=(800, 600), color=(255, 255, 255)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def pdf_bytes(texts=("Metformin 500 mg twice daily", "Review in 4 weeks")):
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def make_patient(client):
    resp = client.post("/v1/patients", headers=HEADERS, json={
        "full_name": "Audit Patient", "date_of_birth": "1970-01-01", "sex": "female",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def upload_record(client, patient_id, filename, content_type, data, source_type="lab_report"):
    init = client.post(f"/v1/patients/{patient_id}/records/upload", headers=HEADERS,
                       json={"filename": filename, "content_type": content_type, "source_type": source_type})
    assert init.status_code == 201, init.text
    record_id = init.json()["record_id"]
    put = client.put(init.json()["upload_url"].replace("http://localhost:8000", ""), headers=HEADERS, content=data)
    assert put.status_code == 204, put.text
    job = client.post(f"/v1/records/{record_id}/complete", headers=HEADERS)
    assert job.status_code == 202, job.text
    return record_id, job.json()["id"]


def get_record(record_id):
    with SessionLocal() as db:
        record = db.get(MedicalRecord, record_id)
        db.expunge(record)
        return record


def get_job(job_id):
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        db.expunge(job)
        return job


def run_worker_for(job_id, worker, max_rounds=10):
    """Drive the worker until THIS job reaches a terminal state.

    Other queued jobs (left by earlier tests) may legitimately be claimed
    first, so we keep pumping rounds until our job completes or fails."""
    for _ in range(max_rounds):
        if get_job(job_id).status in ("completed", "failed"):
            return
        if not worker.process_next():
            break
    assert get_job(job_id).status in ("completed", "failed"), "job never reached a terminal state"


# --- happy path --------------------------------------------------------------

def test_image_upload_runs_to_ready(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "strip.png", "image/png", png_bytes())

    run_worker_for(job_id, Worker(engine=FakeEngine()))

    assert get_record(record_id).status.value == "ready"
    ocr = client.get(f"/v1/records/{record_id}/ocr", headers=DOCTOR)
    assert ocr.status_code == 200
    body = ocr.json()
    assert "Metformin" in body["raw_text"]
    assert body["engine"] == "fake"
    assert body["page_count"] == 1
    assert body["result_json"]["pages"][0]["lines"][0]["confidence"] == 0.95


def test_low_confidence_marks_needs_review(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "scan.png", "image/png", png_bytes())

    run_worker_for(job_id, Worker(engine=FakeEngine(confidence=0.61)))

    assert get_record(record_id).status.value == "needs_review"
    ocr = client.get(f"/v1/records/{record_id}/ocr", headers=DOCTOR).json()
    assert ocr["result_json"]["pages"][0]["lines"][0]["needs_review"] is True


def test_digital_pdf_via_pdftext_engine(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "report.pdf", "application/pdf", pdf_bytes())

    run_worker_for(job_id, Worker(engine=PdfTextEngine()))

    assert get_record(record_id).status.value == "ready"
    ocr = client.get(f"/v1/records/{record_id}/ocr", headers=DOCTOR).json()
    assert "Metformin 500 mg twice daily" in ocr["raw_text"]
    assert ocr["page_count"] == 2
    # embedded text layer: honest absence of confidence, not an invented score
    line = ocr["result_json"]["pages"][0]["lines"][0]
    assert line["confidence"] is None
    assert line["needs_review"] is False


def test_multipage_pdf_rasterised_one_page_fails(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "multi.pdf", "application/pdf", pdf_bytes())

    engine = FakeEngine(fail_pages={2})
    run_worker_for(job_id, Worker(engine=engine))

    assert engine.calls == [1, 2]  # both pages attempted individually
    assert get_record(record_id).status.value == "needs_review"
    ocr = client.get(f"/v1/records/{record_id}/ocr", headers=DOCTOR).json()
    pages = ocr["result_json"]["pages"]
    assert pages[0]["status"] == "ok"
    assert pages[1]["status"] == "failed"
    # page 1 text survives page 2's failure
    assert "Metformin" in ocr["raw_text"]
    assert ocr["result_json"]["metrics"]["failed_pages"] == 1


# --- failure paths -----------------------------------------------------------

def test_engine_failure_retries_then_fails_and_record_not_stuck(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "photo.jpg", "image/jpeg", png_bytes())

    worker = Worker(engine=FakeEngine(raise_error=OcrError("ocr_failure", "engine exploded", retryable=True)))
    run_worker_for(job_id, worker)  # retries up to OCR_MAX_RETRIES, then fails

    job = get_job(job_id)
    assert job.status == "failed"
    assert job.error_code == "ocr_failure"
    assert job.attempt_count == 3
    # the record must never be stuck in processing
    assert get_record(record_id).status.value == "failed"


def test_corrupt_image_fails_permanently_without_retry(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "broken.png", "image/png", b"not an image at all")

    run_worker_for(job_id, Worker(engine=FakeEngine()))

    job = get_job(job_id)
    assert job.status == "failed"
    assert job.error_code == "corrupt_document"
    assert job.attempt_count == 1  # no pointless retries of a permanent problem
    assert get_record(record_id).status.value == "failed"


def test_expired_lease_is_requeued_then_failed(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "scan.png", "image/png", png_bytes())
    worker = Worker(engine=FakeEngine())

    # simulate a worker crash: job stuck in processing with an expired lease
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        job.status = "processing"
        job.attempt_count = 1
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()

    with SessionLocal() as db:
        assert worker.reap_expired_leases(db) == 1
    assert get_job(job_id).status == "queued"

    # lease expires again with attempts exhausted -> permanent failure
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        job.status = "processing"
        job.attempt_count = 3
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()
    with SessionLocal() as db:
        worker.reap_expired_leases(db)
    assert get_job(job_id).status == "failed"
    assert get_record(record_id).status.value == "failed"


def test_retry_endpoint_requeues_failed_job(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "photo.png", "image/png", png_bytes())

    broken = Worker(engine=FakeEngine(raise_error=OcrError("transient", "disk hiccup", retryable=True)))
    run_worker_for(job_id, broken)  # exhausts the retry budget
    assert get_job(job_id).status == "failed"

    retry = client.post(f"/v1/jobs/{job_id}/retry", headers=DOCTOR)
    assert retry.status_code == 202
    assert retry.json()["status"] == "queued"

    run_worker_for(job_id, Worker(engine=FakeEngine()))
    assert get_job(job_id).status == "completed"
    assert get_record(record_id).status.value == "ready"


def test_retry_rejects_non_failed_job(client):
    patient_id = make_patient(client)
    _, job_id = upload_record(client, patient_id, "queued.png", "image/png", png_bytes())
    resp = client.post(f"/v1/jobs/{job_id}/retry", headers=DOCTOR)
    assert resp.status_code == 409


def test_complete_is_idempotent_for_active_job(client):
    patient_id = make_patient(client)
    init = client.post(f"/v1/patients/{patient_id}/records/upload", headers=HEADERS,
                       json={"filename": "doc.png", "content_type": "image/png"})
    record_id = init.json()["record_id"]
    client.put(init.json()["upload_url"].replace("http://localhost:8000", ""), headers=HEADERS, content=png_bytes())
    first = client.post(f"/v1/records/{record_id}/complete", headers=HEADERS).json()
    second = client.post(f"/v1/records/{record_id}/complete", headers=HEADERS).json()
    assert first["id"] == second["id"]


def test_complete_without_bytes_is_conflict(client):
    patient_id = make_patient(client)
    init = client.post(f"/v1/patients/{patient_id}/records/upload", headers=HEADERS,
                       json={"filename": "doc.png", "content_type": "image/png"})
    resp = client.post(f"/v1/records/{init.json()['record_id']}/complete", headers=HEADERS)
    assert resp.status_code == 409


# --- validation at the API ----------------------------------------------------

def test_docx_rejected_at_upload(client):
    patient_id = make_patient(client)
    resp = client.post(f"/v1/patients/{patient_id}/records/upload", headers=HEADERS,
                       json={"filename": "notes.docx", "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"})
    assert resp.status_code == 415


def test_mime_extension_mismatch_rejected(client):
    patient_id = make_patient(client)
    resp = client.post(f"/v1/patients/{patient_id}/records/upload", headers=HEADERS,
                       json={"filename": "report.pdf", "content_type": "image/png"})
    assert resp.status_code == 415


def test_oversized_upload_rejected(client):
    patient_id = make_patient(client)
    init = client.post(f"/v1/patients/{patient_id}/records/upload", headers=HEADERS,
                       json={"filename": "huge.png", "content_type": "image/png"})
    big = b"\x00" * (21 * 1024 * 1024)
    resp = client.put(init.json()["upload_url"].replace("http://localhost:8000", ""), headers=HEADERS, content=big)
    assert resp.status_code == 413


def test_pdf_over_page_limit_fails_cleanly(client):
    doc = pymupdf.open()
    for _ in range(31):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "long.pdf", "application/pdf", data)

    run_worker_for(job_id, Worker(engine=FakeEngine()))

    assert get_job(job_id).error_code == "too_large"
    assert get_record(record_id).status.value == "failed"


# --- access control, original file, corrections -------------------------------

def test_record_file_served_and_role_guarded(client):
    patient_id = make_patient(client)
    record_id, _ = upload_record(client, patient_id, "strip.png", "image/png", png_bytes())

    ok = client.get(f"/v1/records/{record_id}/file", headers=DOCTOR)
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("image/png")

    denied = client.get(f"/v1/records/{record_id}/file", headers={"X-User-Role": "admin"})
    assert denied.status_code == 403


def test_ocr_correction_preserves_raw_text_and_approval_is_doctor_only(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "rx.png", "image/png", png_bytes())
    run_worker_for(job_id, Worker(engine=FakeEngine(confidence=0.61)))

    before = client.get(f"/v1/records/{record_id}/ocr", headers=DOCTOR).json()

    denied = client.put(f"/v1/records/{record_id}/ocr", headers=HEADERS,
                        json={"corrected_text": "Metformin 500 mg", "reviewer": "Arun Kumar", "approve": True})
    assert denied.status_code == 403

    corrected = client.put(f"/v1/records/{record_id}/ocr", headers=DOCTOR,
                           json={"corrected_text": "Metformin 500 mg", "reviewer": "Dr. Rhea Menon", "approve": True})
    assert corrected.status_code == 200
    body = corrected.json()
    assert body["raw_text"] == before["raw_text"]  # original engine evidence untouched
    assert body["corrected_text"] == "Metformin 500 mg"
    assert body["review_status"] == "approved"
    assert body["reviewed_by"] == "Dr. Rhea Menon"


# --- second adversarial pass -------------------------------------------------

def test_pdftext_engine_fails_clearly_on_image(client):
    """An engine that cannot handle a document type must fail loudly."""
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "photo.png", "image/png", png_bytes())

    run_worker_for(job_id, Worker(engine=PdfTextEngine()))

    job = get_job(job_id)
    assert job.status == "failed"
    assert job.error_code == "unsupported_format"
    assert get_record(record_id).status.value == "failed"


def test_processing_timeout_is_retryable_then_fails(client):
    from app.config import Settings

    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "slow.pdf", "application/pdf", pdf_bytes())

    worker = Worker(engine=FakeEngine())
    worker.settings = Settings(max_processing_seconds=0, ocr_max_retries=2)  # every page check trips
    run_worker_for(job_id, worker)

    job = get_job(job_id)
    assert job.status == "failed"
    assert job.error_code == "timeout"
    assert job.attempt_count == 2
    assert get_record(record_id).status.value == "failed"


def test_concurrent_claim_has_single_winner(client):
    """Two workers racing for one job: the guarded UPDATE lets only one win."""
    patient_id = make_patient(client)
    _, job_id = upload_record(client, patient_id, "race.png", "image/png", png_bytes())

    worker_a = Worker(engine=FakeEngine())
    worker_b = Worker(engine=FakeEngine())

    with SessionLocal() as db_a, SessionLocal() as db_b:
        claimed_a = worker_a.claim_next(db_a)
        claimed_b = worker_b.claim_next(db_b)  # must lose: job already processing

    winners = [c for c in (claimed_a, claimed_b) if c is not None]
    assert len(winners) == 1
    assert winners[0].id == job_id
    assert get_job(job_id).attempt_count == 1  # claimed exactly once


def test_missing_file_bytes_fail_as_invalid_input(client):
    """Job created, then the file disappears: permanent, classified failure."""
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "ghost.png", "image/png", png_bytes())

    record = get_record(record_id)
    from pathlib import Path
    from app.config import get_settings
    Path(get_settings().upload_dir, f"{record.id}-{record.filename}").unlink()

    run_worker_for(job_id, Worker(engine=FakeEngine()))

    job = get_job(job_id)
    assert job.status == "failed"
    assert job.error_code == "invalid_input"
    assert job.attempt_count == 1  # permanent: no retries


def test_reapproval_after_new_correction_replaces_text_but_not_raw(client):
    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "rx2.png", "image/png", png_bytes())
    run_worker_for(job_id, Worker(engine=FakeEngine(confidence=0.9)))
    before = client.get(f"/v1/records/{record_id}/ocr", headers=DOCTOR).json()

    client.put(f"/v1/records/{record_id}/ocr", headers=DOCTOR,
               json={"corrected_text": "First correction", "reviewer": "Dr. Rhea Menon", "approve": False})
    second = client.put(f"/v1/records/{record_id}/ocr", headers=DOCTOR,
                        json={"corrected_text": "Final correction", "reviewer": "Dr. Rhea Menon", "approve": True})
    body = second.json()
    assert body["corrected_text"] == "Final correction"
    assert body["review_status"] == "approved"
    assert body["raw_text"] == before["raw_text"]


def test_empty_transcription_is_needs_review_not_ready(client):
    """A scan with no detectable text must not look 'ready' — nothing to verify."""

    class BlankEngine(FakeEngine):
        def ocr_image(self, image_path, page_number):
            return EnginePage(page_number=page_number, lines=[])

    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "blank.png", "image/png", png_bytes())
    run_worker_for(job_id, Worker(engine=BlankEngine()))

    assert get_job(job_id).status == "completed"
    assert get_record(record_id).status.value == "needs_review"


def test_production_env_refuses_header_auth(client, monkeypatch):
    """Outside development, the dev role header must not be accepted at all."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    try:
        resp = client.get("/health")  # public
        assert resp.status_code == 200
        denied = client.get("/v1/patients/anything", headers=DOCTOR)
        assert denied.status_code == 503
    finally:
        monkeypatch.delenv("APP_ENV")
        get_settings.cache_clear()
