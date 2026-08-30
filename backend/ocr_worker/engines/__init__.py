"""Engine registry. OCR_ENGINE selects the implementation; the rest of
the pipeline (API, DB schema, frontend) is engine-agnostic."""
from __future__ import annotations

from .base import EngineLine, EnginePage, OcrEngine, OcrError

__all__ = ["EngineLine", "EnginePage", "OcrEngine", "OcrError", "get_engine"]


def get_engine(name: str) -> OcrEngine:
    if name == "paddle":
        from .paddle import PaddleEngine

        return PaddleEngine()
    if name == "pdftext":
        from .pdftext import PdfTextEngine

        return PdfTextEngine()
    raise OcrError("model_init_failure", f"Unknown OCR engine: {name!r}", retryable=False)
