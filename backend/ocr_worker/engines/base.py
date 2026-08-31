"""OCR engine abstraction.

The worker talks to engines only through these types, so a new engine
(e.g. a vision-LLM transcription service) can be added without touching
the API, database or frontend. Engines transcribe what is visible; they
must never infer clinical facts, and must report confidence honestly
(None when the engine has no meaningful confidence signal).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


# Error categories mirror app.models.JOB_ERROR_CATEGORIES. Kept as plain
# strings here so the worker package does not depend on the API models.
class OcrError(Exception):
    """An OCR pipeline failure with a stable, patient-safe category."""

    def __init__(self, category: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        # message is stored on the job; keep it free of document content.


@dataclass
class EngineLine:
    text: str
    confidence: float | None = None  # None = engine provides no confidence
    bbox: list | None = None
    polygon: list | None = None
    needs_review: bool | None = None  # None = let the normalizer decide


@dataclass
class EnginePage:
    page_number: int
    lines: list[EngineLine] = field(default_factory=list)
    status: str = "ok"  # "ok" | "failed"
    error: str | None = None


@runtime_checkable
class OcrEngine(Protocol):
    name: str
    model: str

    def warmup(self) -> None:
        """Initialise/download models. Raise OcrError(category='model_init_failure')."""
        ...

    def ocr_image(self, image_path: Path, page_number: int) -> EnginePage:
        """Transcribe one prepared page image."""
        ...
