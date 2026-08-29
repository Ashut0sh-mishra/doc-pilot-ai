from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import RecordStatus, SourceType


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    date_of_birth: date
    sex: str
    phone: str | None = None
    blood_group: str | None = None


class PatientRead(PatientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class MedicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    dose: str | None = None
    frequency: str | None = None
    status: str = "current"
    verification_status: str = "patient_reported"
    source_record_id: str | None = None


class MedicationRead(MedicationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    patient_id: str


class RecordUploadRequest(BaseModel):
    filename: str
    content_type: str
    source_type: SourceType = SourceType.other
    captured_at: date | None = None


class RecordUploadResponse(BaseModel):
    record_id: str
    storage_key: str
    upload_url: str
    expires_in_seconds: int = 900


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    patient_id: str
    filename: str
    content_type: str
    source_type: SourceType
    status: RecordStatus
    captured_at: date | None
    uploaded_at: datetime


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    record_id: str
    kind: str
    status: str
    error: str | None
    created_at: datetime
    completed_at: datetime | None


class OcrResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    record_id: str
    schema_version: str
    engine: str
    model: str
    language: str
    raw_text: str
    mean_confidence: float | None
    result_json: dict
    created_at: datetime


class SummaryRead(BaseModel):
    patient_id: str
    evidence_coverage: int
    records_total: int
    medications_total: int
    unverified_medications: int
    record_gaps: list[str]
    notice: str
