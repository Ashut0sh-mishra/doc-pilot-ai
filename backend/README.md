# DocPilot API

FastAPI foundation for the patient and doctor apps.

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API documentation.

The development API uses SQLite. Set `DATABASE_URL` to a PostgreSQL connection string in production. The `X-User-Role` header is a temporary development boundary; replace it with validated JWT claims before handling real data.

> The dev database is created with `create_all` (no migrations yet). If the
> schema changes, stop the API and move `docpilot.db` aside; it is recreated
> on startup.

## Implemented API areas

- Patient profiles
- Medication history
- Record upload initiation and metadata (validated: extension, MIME, size)
- Original document download for side-by-side review (`GET /v1/records/{id}/file`)
- OCR job creation, status, idempotent completion, and retry of failed jobs
- OCR result retrieval plus human corrections (`PUT /v1/records/{id}/ocr`); the raw engine output is never overwritten, and approval is doctor-only
- Doctor-only clinical summary endpoint
- Role checks and patient-facing AI restriction

## OCR pipeline

The worker turns uploaded documents into reviewable transcriptions:

```
upload -> validate -> PDF pages rasterised one at a time / image normalised
       -> OCR engine -> normalised result (per-page status, per-line
       confidence, review flags) -> ready | needs_review | failed
```

The engine is selected with `OCR_ENGINE` and is fully replaceable:

- `paddle` (default) — PaddleOCR PP-OCRv5 for scanned PDFs and photos, incl. handwriting. Heavy; install `ocr_worker/requirements.txt`.
- `pdftext` — PyMuPDF embedded-text extraction for digital PDFs only. Light, deterministic; reports `confidence: null` honestly instead of inventing scores. Scans/photos need `paddle`.

Job reliability: atomic claiming (two workers cannot take the same job), a lease + per-page heartbeat (a crashed worker's job is requeued, or failed after `OCR_MAX_RETRIES`), error classification (`invalid_input`, `unsupported_format`, `corrupt_document`, `too_large`, `model_init_failure`, `ocr_failure`, `timeout`, `transient`), and page-level fault isolation — one bad page never discards the rest. A failed job always moves its record to `failed`.

```bash
pip install -r requirements.txt -r ocr_worker/requirements.txt
python -m ocr_worker.run --watch    # or a single pass without --watch
```

OCR output is stored as searchable `raw_text` plus canonical schema-versioned JSON (pages, lines, confidence, bounding boxes, polygons, per-page status, review flags). Low-confidence lines are never treated as verified clinical facts, and OCR confidence is never presented as clinical certainty.

Limits are configurable (see `.env.example`): `MAX_UPLOAD_MB`, `MAX_PAGES`, `MAX_PAGE_PIXELS`, `MAX_PROCESSING_SECONDS`, `OCR_MAX_RETRIES`, `JOB_LEASE_SECONDS`, `WORKER_POLL_SECONDS`.

## Tests

```bash
pytest
```

Covers the upload API (validation, roles), the job lifecycle (claim, retry, lease recovery, failure paths), page-level OCR isolation, digital-PDF extraction, corrections/approval, and the normalizer.

Object-storage signing, authentication, consent, tenancy, audit trails, and clinical extraction are the next backend increments.
