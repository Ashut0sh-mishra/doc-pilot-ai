# DocPilot AI

A clinical record-intelligence product that helps patients submit fragmented medical history before a visit and gives clinicians an evidence-linked, structured overview.

- `src/` — React/Vite clinic web dashboard
- `mobile/` — Flutter Android/iOS patient and doctor app
- `backend/` — FastAPI service for patients, records, medications and processing jobs

## Run locally

```bash
npm install
npm run dev
```

Backend (see `backend/README.md`):

```bash
cd backend
pip install -r requirements.txt -r ocr_worker/requirements.txt
uvicorn app.main:app --reload          # API on :8000
python -m ocr_worker.run --watch       # OCR worker (separate terminal)
```

The prototype includes patient and doctor views, record/image upload interactions, a real OCR pipeline with review and correction, a medical timeline, medication reconciliation prompts, missing-record detection, and clinician-only decision support.

> This prototype is not a medical device and does not provide autonomous diagnosis or treatment.
