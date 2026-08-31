"""DocPilot OCR worker.

Polls the database for queued processing jobs and runs the configured
OCR engine over them, one page at a time.

Reliability model:
* Atomic claim: a job moves queued -> processing with an UPDATE guarded
  on status='queued', so two workers can never take the same job.
* Lease + heartbeat: a claimed job holds a lease (job_lease_seconds) that
  the worker renews after every page. If the worker dies, the lease
  expires and the next worker requeues (attempts remain) or fails the job.
* Retry classification: permanent problems (invalid/corrupt/unsupported/
  too large) fail immediately; transient ones (engine error, timeout,
  model download) retry up to ocr_max_retries.
* Page isolation: one failing page is recorded as failed in the result;
  successful pages are kept. The job only fails when no page succeeds.
* A failed job ALWAYS moves its record to 'failed' — a record can never
  be stuck in 'processing'.

Known bound: the lease is renewed between pages, not during one. Keep
job_lease_seconds well above the slowest single-page OCR time.

Logging is structured (key=value) and never includes document content.
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update

from app.config import get_settings
from app.database import Base, SessionLocal, engine as db_engine
from app.models import RETRYABLE_CATEGORIES, MedicalRecord, OcrResult, ProcessingJob, RecordStatus
from ocr_worker.documents import prepare_document, validate_record_file
from ocr_worker.engines import EnginePage, OcrEngine, OcrError, get_engine
from ocr_worker.normalizer import assemble_result

logger = logging.getLogger("docpilot.ocr")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Worker:
    def __init__(self, engine: OcrEngine | None = None):
        self.settings = get_settings()
        self._engine = engine

    @property
    def engine(self) -> OcrEngine:
        if self._engine is None:
            self._engine = get_engine(self.settings.ocr_engine)
        return self._engine

    # --- queue management -------------------------------------------------

    def reap_expired_leases(self, db) -> int:
        """Recover jobs whose worker died mid-processing."""
        now = utcnow()
        stuck = db.scalars(
            select(ProcessingJob).where(
                ProcessingJob.status == "processing",
                ProcessingJob.lease_expires_at < now,
            )
        ).all()
        for job in stuck:
            record = db.get(MedicalRecord, job.record_id)
            if job.attempt_count < self.settings.ocr_max_retries:
                job.status = "queued"
                job.lease_expires_at = None
                job.heartbeat_at = None
                job.error = "Worker stopped responding; job was requeued"
                logger.warning("job_requeued job_id=%s record_id=%s reason=lease_expired attempt=%d",
                               job.id, job.record_id, job.attempt_count)
            else:
                job.status = "failed"
                job.error = "Worker stopped responding and the retry limit was reached"
                job.error_code = "transient"
                job.completed_at = now
                if record:
                    record.status = RecordStatus.failed
                logger.error("job_failed job_id=%s record_id=%s reason=lease_expired attempts=%d",
                             job.id, job.record_id, job.attempt_count)
        if stuck:
            db.commit()
        return len(stuck)

    def claim_next(self, db) -> ProcessingJob | None:
        candidate = db.scalar(
            select(ProcessingJob.id).where(ProcessingJob.status == "queued").order_by(ProcessingJob.created_at).limit(1)
        )
        if candidate is None:
            return None
        now = utcnow()
        result = db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == candidate, ProcessingJob.status == "queued")
            .values(
                status="processing",
                attempt_count=ProcessingJob.attempt_count + 1,
                started_at=now,
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=self.settings.job_lease_seconds),
                completed_at=None,
            )
        )
        db.commit()
        if result.rowcount != 1:
            return None  # another worker claimed it first
        return db.get(ProcessingJob, candidate)

    def heartbeat(self, db, job: ProcessingJob) -> None:
        now = utcnow()
        job.heartbeat_at = now
        job.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
        db.commit()

    # --- job execution ----------------------------------------------------

    def process_next(self) -> bool:
        with SessionLocal() as db:
            self.reap_expired_leases(db)
            job = self.claim_next(db)
            if job is None:
                return False
            logger.info("job_claimed job_id=%s record_id=%s attempt=%d", job.id, job.record_id, job.attempt_count)
            self.run_job(db, job)
            return True

    def run_job(self, db, job: ProcessingJob) -> None:
        started = time.monotonic()
        record = db.get(MedicalRecord, job.record_id)
        try:
            if record is None:
                raise OcrError("invalid_input", "Medical record does not exist", retryable=False)
            source = validate_record_file(record, self.settings)
            pages = self._extract_pages(db, job, source, started)
            self._store_result(db, job, record, pages, started)
        except OcrError as exc:
            self._handle_failure(db, job, record, exc)
        except Exception as exc:  # unexpected: classify as transient, retry
            logger.exception("job_error job_id=%s record_id=%s", job.id, job.record_id)
            self._handle_failure(db, job, record, OcrError("transient", f"Unexpected error: {exc}"[:500], retryable=True))

    def _extract_pages(self, db, job: ProcessingJob, source: Path, started: float) -> list[EnginePage]:
        is_pdf = source.suffix.lower() == ".pdf"
        # Digital-text engines read the PDF directly; visual engines get
        # rasterised pages. Either way, pages are processed one at a time.
        if is_pdf and hasattr(self.engine, "extract_pdf"):
            logger.info("extract_text_layer job_id=%s record_id=%s engine=%s", job.id, job.record_id, self.engine.name)
            return self.engine.extract_pdf(source, self.settings.max_pages)

        pages: list[EnginePage] = []
        with prepare_document(source, self.settings) as (total_pages, prepared):
            logger.info("document_prepared job_id=%s record_id=%s pages=%d", job.id, job.record_id, total_pages)
            for page in prepared:
                if time.monotonic() - started > self.settings.max_processing_seconds:
                    raise OcrError("timeout", f"Exceeded {self.settings.max_processing_seconds}s processing limit", retryable=True)
                self.heartbeat(db, job)
                if page.image_path is None:
                    pages.append(EnginePage(page_number=page.page_number, status="failed", error=page.error))
                    logger.warning("page_failed job_id=%s record_id=%s page=%d stage=render",
                                   job.id, job.record_id, page.page_number)
                    continue
                page_started = time.monotonic()
                try:
                    result = self.engine.ocr_image(page.image_path, page.page_number)
                except OcrError as exc:
                    if exc.category == "model_init_failure" or not exc.retryable:
                        raise  # engine-level or permanent problem — handle at job level
                    result = EnginePage(page_number=page.page_number, status="failed", error=exc.args[0])
                pages.append(result)
                logger.info(
                    "page_completed job_id=%s record_id=%s page=%d status=%s lines=%d duration_ms=%d",
                    job.id, job.record_id, page.page_number, result.status,
                    len(result.lines), int((time.monotonic() - page_started) * 1000),
                )
        if pages and all(p.status == "failed" for p in pages):
            raise OcrError("ocr_failure", "OCR failed on every page", retryable=True)
        return pages

    def _store_result(self, db, job: ProcessingJob, record: MedicalRecord, pages: list[EnginePage], started: float) -> None:
        normalized = assemble_result(record.id, self.engine.name, self.engine.model, pages)
        # Optional LLM structuring pass — separate from OCR, unverified,
        # and never allowed to fail or alter the transcription.
        if self.settings.groq_extraction_enabled and normalized["full_text"]:
            from ocr_worker.extraction import extract_clinical_structure

            extraction = extract_clinical_structure(
                normalized["full_text"], self.settings, poster=getattr(self.engine, "_poster", None)
            )
            if extraction:
                normalized["extraction"] = extraction
                logger.info("extraction_completed job_id=%s record_id=%s", job.id, record.id)
        stored = db.scalar(select(OcrResult).where(OcrResult.record_id == record.id)) or OcrResult(record_id=record.id, result_json={})
        stored.schema_version = normalized["schema_version"]
        stored.engine = self.engine.name
        stored.model = self.engine.model
        stored.raw_text = normalized["full_text"]
        stored.mean_confidence = normalized["metrics"]["mean_confidence"]
        stored.page_count = normalized["document"]["page_count"]
        stored.result_json = normalized
        # A re-run discards previous review state only if the text changed.
        if stored.corrected_text and stored.corrected_text == stored.raw_text:
            stored.corrected_text = None
        db.add(stored)

        metrics = normalized["metrics"]
        # Empty transcription (blank/garbage scan) can never be "ready" —
        # a human must look at the document. Confidence flags likewise.
        needs_human = metrics["low_confidence_lines"] or metrics["failed_pages"] or metrics["total_lines"] == 0
        record.status = RecordStatus.review if needs_human else RecordStatus.ready
        job.status = "completed"
        job.error = None
        job.error_code = None
        job.completed_at = utcnow()
        db.commit()
        logger.info(
            "job_completed job_id=%s record_id=%s record_status=%s pages=%d lines=%d low_confidence_lines=%d failed_pages=%d duration_ms=%d",
            job.id, record.id, record.status.value, normalized["document"]["page_count"],
            metrics["total_lines"], metrics["low_confidence_lines"], metrics["failed_pages"],
            int((time.monotonic() - started) * 1000),
        )

    def _handle_failure(self, db, job: ProcessingJob, record: MedicalRecord | None, exc: OcrError) -> None:
        retryable = exc.retryable and exc.category in RETRYABLE_CATEGORIES
        if retryable and job.attempt_count < self.settings.ocr_max_retries:
            job.status = "queued"
            job.lease_expires_at = None
            job.heartbeat_at = None
            job.error = str(exc)[:1000]
            job.error_code = exc.category
            db.commit()
            logger.warning("job_retried job_id=%s record_id=%s category=%s attempt=%d",
                           job.id, job.record_id, exc.category, job.attempt_count)
            return
        job.status = "failed"
        job.error = str(exc)[:1000]
        job.error_code = exc.category
        job.completed_at = utcnow()
        if record is not None:
            record.status = RecordStatus.failed
        db.commit()
        logger.error("job_failed job_id=%s record_id=%s category=%s attempts=%d",
                     job.id, job.record_id, exc.category, job.attempt_count)


def main() -> None:
    parser = argparse.ArgumentParser(description="DocPilot OCR worker")
    parser.add_argument("--watch", action="store_true", help="Continuously poll for queued jobs")
    parser.add_argument("--interval", type=float, default=None, help="Poll interval in seconds")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    interval = args.interval if args.interval is not None else settings.worker_poll_seconds

    Base.metadata.create_all(bind=db_engine)
    worker = Worker()
    logger.info("worker_started engine=%s poll_interval=%.1fs lease=%ds max_retries=%d",
                settings.ocr_engine, interval, settings.job_lease_seconds, settings.ocr_max_retries)
    while True:
        try:
            processed = worker.process_next()
        except Exception:
            logger.exception("worker_poll_error — continuing")
            processed = False
        if not args.watch:
            break
        if not processed:
            time.sleep(interval)


if __name__ == "__main__":
    main()
