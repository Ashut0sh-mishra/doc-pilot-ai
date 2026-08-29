import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import require_role
from .config import get_settings
from .database import Base, engine, get_db
from .models import MedicalRecord, Medication, OcrResult, Patient, ProcessingJob, RecordStatus
from .schemas import (
    JobRead, MedicationCreate, MedicationRead, OcrResultRead, PatientCreate, PatientRead,
    RecordRead, RecordUploadRequest, RecordUploadResponse, SummaryRead,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def patient_or_404(patient_id: str, db: Session) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.post("/v1/patients", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor", "admin"))):
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@app.get("/v1/patients/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: str, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor", "admin"))):
    return patient_or_404(patient_id, db)


@app.post("/v1/patients/{patient_id}/medications", response_model=MedicationRead, status_code=201)
def add_medication(patient_id: str, payload: MedicationCreate, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    patient_or_404(patient_id, db)
    medication = Medication(patient_id=patient_id, **payload.model_dump())
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


@app.get("/v1/patients/{patient_id}/medications", response_model=list[MedicationRead])
def list_medications(patient_id: str, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    patient_or_404(patient_id, db)
    return db.scalars(select(Medication).where(Medication.patient_id == patient_id)).all()


@app.post("/v1/patients/{patient_id}/records/upload", response_model=RecordUploadResponse, status_code=201)
def initiate_upload(patient_id: str, payload: RecordUploadRequest, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    patient_or_404(patient_id, db)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", payload.filename)
    storage_key = f"patients/{patient_id}/records/{uuid.uuid4()}-{safe_name}"
    record = MedicalRecord(patient_id=patient_id, storage_key=storage_key, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    # Production replaces this local URL with an S3/GCS presigned PUT URL.
    upload_url = f"http://localhost:8000/v1/dev-uploads/{record.id}"
    return RecordUploadResponse(record_id=record.id, storage_key=storage_key, upload_url=upload_url)


@app.put("/v1/dev-uploads/{record_id}", status_code=204)
async def dev_upload(record_id: str, request: Request, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    """Receive file bytes locally. Production will use a presigned object-storage URL."""
    if settings.app_env != "development":
        raise HTTPException(status_code=404, detail="Not found")
    record = db.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    body = await request.body()
    if len(body) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit")
    upload_root = Path(settings.upload_dir).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    (upload_root / f"{record.id}-{Path(record.filename).name}").write_bytes(body)


@app.post("/v1/records/{record_id}/complete", response_model=JobRead, status_code=202)
def complete_upload(record_id: str, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    record = db.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    record.status = RecordStatus.processing
    job = ProcessingJob(record_id=record_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@app.get("/v1/patients/{patient_id}/records", response_model=list[RecordRead])
def list_records(patient_id: str, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    patient_or_404(patient_id, db)
    return db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == patient_id).order_by(MedicalRecord.uploaded_at.desc())).all()


@app.get("/v1/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/v1/records/{record_id}/ocr", response_model=OcrResultRead)
def get_ocr_result(record_id: str, db: Session = Depends(get_db), _: str = Depends(require_role("patient", "doctor"))):
    result = db.scalar(select(OcrResult).where(OcrResult.record_id == record_id))
    if not result:
        raise HTTPException(status_code=404, detail="OCR result is not ready")
    return result


@app.get("/v1/patients/{patient_id}/clinical-summary", response_model=SummaryRead)
def clinical_summary(patient_id: str, db: Session = Depends(get_db), _: str = Depends(require_role("doctor"))):
    patient_or_404(patient_id, db)
    records = db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == patient_id)).all()
    medicines = db.scalars(select(Medication).where(Medication.patient_id == patient_id, Medication.status == "current")).all()
    verified = sum(record.status == RecordStatus.ready for record in records)
    coverage = round((verified / len(records)) * 100) if records else 0
    return SummaryRead(
        patient_id=patient_id,
        evidence_coverage=coverage,
        records_total=len(records),
        medications_total=len(medicines),
        unverified_medications=sum(m.verification_status != "clinician_verified" for m in medicines),
        record_gaps=[],
        notice="Decision support only. Verify source evidence and use independent clinical judgement.",
    )
