from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import MedicalRecord, OcrResult, ProcessingJob, RecordStatus
from ocr_worker.normalizer import normalize_paddle_results


def input_path(record: MedicalRecord) -> Path:
    settings = get_settings()
    return Path(settings.upload_dir).resolve() / f"{record.id}-{Path(record.filename).name}"


def process_next() -> bool:
    with SessionLocal() as db:
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.status == "queued").order_by(ProcessingJob.created_at))
        if not job:
            return False
        job.status = "processing"
        db.commit()

        try:
            record = db.get(MedicalRecord, job.record_id)
            if not record:
                raise RuntimeError("Medical record does not exist")
            source = input_path(record)
            if not source.exists():
                raise FileNotFoundError(f"Uploaded file not found: {source}")

            # Lazy import keeps the API environment independent of the heavy OCR runtime.
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(
                ocr_version="PP-OCRv5",
                text_detection_model_name="PP-OCRv5_server_det",
                text_recognition_model_name="PP-OCRv5_server_rec",
                use_doc_orientation_classify=True,
                use_doc_unwarping=True,
                use_textline_orientation=True,
                device="cpu",
            )
            normalized = normalize_paddle_results(list(ocr.predict(str(source))), record.id)
            stored = db.scalar(select(OcrResult).where(OcrResult.record_id == record.id)) or OcrResult(record_id=record.id, result_json={})
            stored.raw_text = normalized["full_text"]
            stored.mean_confidence = normalized["metrics"]["mean_confidence"]
            stored.result_json = normalized
            db.add(stored)
            record.status = RecordStatus.review if normalized["metrics"]["low_confidence_lines"] else RecordStatus.ready
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)[:4000]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="DocPilot PaddleOCR worker")
    parser.add_argument("--watch", action="store_true", help="Continuously poll for queued jobs")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    while True:
        processed = process_next()
        if not args.watch:
            break
        if not processed:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
