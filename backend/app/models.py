import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecordStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    review = "needs_review"
    ready = "ready"
    failed = "failed"


class SourceType(str, enum.Enum):
    consultation = "consultation"
    lab = "lab_report"
    imaging = "imaging"
    prescription = "prescription"
    medicine_photo = "medicine_photo"
    discharge = "discharge_summary"
    other = "other"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(30))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    records: Mapped[list["MedicalRecord"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    medications: Mapped[list["Medication"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), default=SourceType.other)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    status: Mapped[RecordStatus] = mapped_column(Enum(RecordStatus), default=RecordStatus.uploaded)
    captured_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    patient: Mapped[Patient] = relationship(back_populates="records")


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    dose: Mapped[str | None] = mapped_column(String(80), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="current")
    verification_status: Mapped[str] = mapped_column(String(30), default="patient_reported")
    source_record_id: Mapped[str | None] = mapped_column(ForeignKey("medical_records.id"), nullable=True)
    patient: Mapped[Patient] = relationship(back_populates="medications")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id: Mapped[str] = mapped_column(ForeignKey("medical_records.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="ocr_extract")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OcrResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id: Mapped[str] = mapped_column(ForeignKey("medical_records.id"), unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    engine: Mapped[str] = mapped_column(String(60), default="paddleocr")
    model: Mapped[str] = mapped_column(String(100), default="PP-OCRv5")
    language: Mapped[str] = mapped_column(String(30), default="en")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
