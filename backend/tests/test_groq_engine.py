"""Tests for the opt-in Groq vision engine + extraction pass.

All HTTP is mocked via the engine's poster seam — no network, no API key.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_docpilot.db")

from types import SimpleNamespace

from app.config import Settings
from ocr_worker.engines import OcrError, get_engine
from ocr_worker.engines.groq_vision import GroqVisionEngine
from ocr_worker.extraction import extract_clinical_structure
from ocr_worker.run import Worker

from tests.test_worker import get_job, get_record, make_patient, png_bytes, run_worker_for, upload_record


def groq_settings(**overrides):
    # keep the real backend/.env keys out of tests: explicit None wins over env
    return Settings(groq_api_key="test-key-not-real", groq_api_keys=None, **overrides)


class FakeGroq:
    """Scripted Groq endpoint: serves queued responses, records payloads."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def __call__(self, url, headers, json, timeout):
        assert headers["Authorization"] == "Bearer test-key-not-real"
        self.payloads.append(json)
        item = self.responses.pop(0)
        if isinstance(item, tuple):
            status, body, hdrs = item
            return SimpleNamespace(status_code=status, headers=hdrs, json=lambda: body)
        return SimpleNamespace(status_code=200, headers={}, json=lambda: item)


def chat(text, finish="stop"):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}]}


def test_engine_requires_api_key():
    engine = GroqVisionEngine(settings=Settings(groq_api_key=None, groq_api_keys=None))
    try:
        engine.warmup()
        raise AssertionError("should have raised")
    except OcrError as exc:
        assert exc.category == "model_init_failure"
        assert exc.retryable is False  # missing key is permanent, not retried


def test_transcription_contract_parsing():
    poster = FakeGroq([chat("Tab. Metformin 500 mg\n1-0-1 after food\nTab. [illegible] 20 mg")])
    engine = GroqVisionEngine(settings=groq_settings(), poster=poster)

    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes())
        tmp_path = Path(tmp.name)
    page = engine.ocr_image(tmp_path, 1)
    tmp_path.unlink()

    assert len(page.lines) == 3
    # honest: no confidence scores from an LLM
    assert all(line.confidence is None for line in page.lines)
    # [illegible] preserved verbatim and flagged — never guessed
    assert page.lines[2].text == "Tab. [illegible] 20 mg"
    assert page.lines[2].needs_review is True
    assert page.lines[0].needs_review is False
    # pure transcription: temperature 0, system contract present
    payload = poster.payloads[0]
    assert payload["temperature"] == 0
    assert "[illegible]" in payload["messages"][0]["content"]


def test_length_finish_retries_with_bigger_budget():
    poster = FakeGroq([
        chat("partial text", finish="length"),
        chat("full text line 1\nfull text line 2"),
    ])
    engine = GroqVisionEngine(settings=groq_settings(), poster=poster)
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes())
        tmp_path = Path(tmp.name)
    page = engine.ocr_image(tmp_path, 1)
    tmp_path.unlink()

    assert [p["max_completion_tokens"] for p in poster.payloads] == [1500, 4000]
    assert len(page.lines) == 2


def test_rate_limit_backoff_then_success(monkeypatch):
    import ocr_worker.engines.groq_vision as gv
    monkeypatch.setattr(gv.time, "sleep", lambda s: None)  # don't actually wait
    poster = FakeGroq([(429, {}, {"retry-after": "0"}), chat("ok line")])
    engine = GroqVisionEngine(settings=groq_settings(), poster=poster)
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes())
        tmp_path = Path(tmp.name)
    page = engine.ocr_image(tmp_path, 1)
    tmp_path.unlink()
    assert page.lines[0].text == "ok line"


def test_full_job_with_groq_engine(client):
    poster = FakeGroq([chat("Metformin 500 mg\nTake [illegible] daily")])
    settings = groq_settings()
    worker = Worker(engine=GroqVisionEngine(settings=settings, poster=poster))
    worker.settings = settings

    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "rx-groq.png", "image/png", png_bytes())
    run_worker_for(job_id, worker)

    assert get_job(job_id).status == "completed"
    assert get_record(record_id).status.value == "needs_review"  # the [illegible] line
    ocr = client.get(f"/v1/records/{record_id}/ocr", headers={"X-User-Role": "doctor"}).json()
    assert ocr["engine"] == "groq-vision"
    assert ocr["mean_confidence"] is None  # no invented confidence


def test_extraction_is_unverified_and_never_alters_raw_text(client):
    extraction_body = chat('{"medications": [{"name": "Metformin", "dose": "500 mg", "frequency": null, "uncertain": false}]}')
    poster = FakeGroq([chat("Metformin 500 mg"), extraction_body])
    settings = groq_settings(groq_extraction_enabled=True)
    worker = Worker(engine=GroqVisionEngine(settings=settings, poster=poster))
    worker.settings = settings

    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "rx-extract.png", "image/png", png_bytes())
    run_worker_for(job_id, worker)

    ocr = client.get(f"/v1/records/{record_id}/ocr", headers={"X-User-Role": "doctor"}).json()
    extraction = ocr["result_json"].get("extraction")
    assert extraction["unverified"] is True
    assert extraction["data"]["medications"][0]["name"] == "Metformin"
    assert ocr["raw_text"] == "Metformin 500 mg"  # untouched by reasoning


def test_extraction_failure_does_not_fail_job(client):
    poster = FakeGroq([chat("Some text"), (500, {}, {})])
    settings = groq_settings(groq_extraction_enabled=True)
    worker = Worker(engine=GroqVisionEngine(settings=settings, poster=poster))
    worker.settings = settings

    patient_id = make_patient(client)
    record_id, job_id = upload_record(client, patient_id, "rx-exfail.png", "image/png", png_bytes())
    run_worker_for(job_id, worker)

    assert get_job(job_id).status == "completed"  # extraction is auxiliary
    ocr = client.get(f"/v1/records/{record_id}/ocr", headers={"X-User-Role": "doctor"}).json()
    assert "extraction" not in ocr["result_json"]


def test_key_pool_rotates_on_rate_limit(monkeypatch):
    import ocr_worker.engines.groq_vision as gv
    monkeypatch.setattr(gv.time, "sleep", lambda s: None)

    seen_keys = []

    def poster(url, headers, json, timeout):
        seen_keys.append(headers["Authorization"])
        if len(seen_keys) == 1:
            return SimpleNamespace(status_code=429, headers={"retry-after": "30"}, json=lambda: {})
        return SimpleNamespace(status_code=200, headers={}, json=lambda: chat("rotated ok"))

    settings = Settings(groq_api_keys="key-a,key-b")
    engine = GroqVisionEngine(settings=settings, poster=poster)
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes())
        tmp_path = Path(tmp.name)
    page = engine.ocr_image(tmp_path, 1)
    tmp_path.unlink()

    assert seen_keys == ["Bearer key-a", "Bearer key-b"]  # rotated, no 30s wait
    assert page.lines[0].text == "rotated ok"
    assert engine._key_index == 1  # sticky on the working key


def test_think_blocks_are_stripped_and_reasoning_disabled():
    poster = FakeGroq([chat("<think>let me read this carefully...</think>\nTab. Metformin 500 mg")])
    engine = GroqVisionEngine(settings=groq_settings(), poster=poster)
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes())
        tmp_path = Path(tmp.name)
    page = engine.ocr_image(tmp_path, 1)
    tmp_path.unlink()

    assert [l.text for l in page.lines] == ["Tab. Metformin 500 mg"]
    assert poster.payloads[0]["reasoning_effort"] == "none"


def test_extraction_returns_none_without_key():
    assert extract_clinical_structure("text", Settings(groq_api_key=None, groq_api_keys=None, groq_extraction_enabled=True)) is None
