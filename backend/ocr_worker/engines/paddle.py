"""PaddleOCR engine (PP-OCRv5). Handles scanned PDFs and photos of
documents, including printed and handwritten English. The heavy paddle
dependency is imported lazily so the FastAPI environment stays light.
"""
from __future__ import annotations

from pathlib import Path

from .base import EngineLine, EnginePage, OcrError


class PaddleEngine:
    name = "paddleocr"
    model = "PP-OCRv5"

    def __init__(self) -> None:
        self._ocr = None

    def warmup(self) -> None:
        if self._ocr is not None:
            return
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrError(
                "model_init_failure",
                "PaddleOCR is not installed in the worker environment "
                "(pip install -r ocr_worker/requirements.txt)",
                retryable=False,
            ) from exc
        try:
            self._ocr = PaddleOCR(
                ocr_version="PP-OCRv5",
                text_detection_model_name="PP-OCRv5_server_det",
                text_recognition_model_name="PP-OCRv5_server_rec",
                use_doc_orientation_classify=True,
                use_doc_unwarping=True,
                use_textline_orientation=True,
                device="cpu",
            )
        except Exception as exc:  # model download/init — often transient
            raise OcrError("model_init_failure", f"PaddleOCR initialisation failed: {exc}", retryable=True) from exc

    def ocr_image(self, image_path: Path, page_number: int) -> EnginePage:
        self.warmup()
        try:
            results = list(self._ocr.predict(str(image_path)))
        except Exception as exc:
            raise OcrError("ocr_failure", f"OCR failed on page {page_number}: {exc}", retryable=True) from exc
        lines: list[EngineLine] = []
        for result in results:
            payload = result.json if hasattr(result, "json") else result
            data = payload.get("res", payload)
            texts = _as_list(data.get("rec_texts"))
            scores = _as_list(data.get("rec_scores"))
            boxes = _as_list(data.get("rec_boxes"))
            polygons = _as_list(data.get("rec_polys"))
            for index, text in enumerate(texts):
                if not text or not str(text).strip():
                    continue
                lines.append(EngineLine(
                    text=str(text),
                    confidence=float(scores[index]) if index < len(scores) else None,
                    bbox=boxes[index] if index < len(boxes) else None,
                    polygon=polygons[index] if index < len(polygons) else None,
                ))
        return EnginePage(page_number=page_number, lines=lines)


def _as_list(value) -> list:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)
