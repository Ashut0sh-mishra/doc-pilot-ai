# DocPilot API

FastAPI foundation for the patient and doctor apps.

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API documentation.

The development API uses SQLite. Set `DATABASE_URL` to a PostgreSQL connection string in production. The `X-User-Role` header is a temporary development boundary; replace it with validated JWT claims before handling real data.

## Implemented API areas

- Patient profiles
- Medication history
- Record upload initiation and metadata
- OCR/extraction job creation and status
- Doctor-only clinical summary endpoint
- Role checks and patient-facing AI restriction

Object-storage signing, OCR workers, authentication, consent, tenancy, audit trails, and clinical extraction are the next backend increments.

## OCR worker

The OCR worker uses open-source PaddleOCR PP-OCRv5 and runs separately on Python 3.12. It supports scanned PDFs and images, including printed and handwritten English. Uploaded records create queued jobs automatically.

```bash
# In a Python 3.12 environment with the API and OCR requirements installed:
python -m ocr_worker.run --watch
```

OCR output is saved twice: searchable `raw_text` and canonical schema-versioned JSON containing pages, lines, confidence scores, bounding boxes, polygons, and review flags. Low-confidence lines are never treated as verified clinical facts.
