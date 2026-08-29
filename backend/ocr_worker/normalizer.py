from __future__ import annotations

from statistics import fmean
from typing import Any


def _list(value: Any) -> list:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def normalize_paddle_results(results: list[Any], record_id: str, model: str = "PP-OCRv5") -> dict:
    """Convert PaddleOCR Result objects/dicts to DocPilot OCR schema 1.0."""
    pages = []
    all_scores: list[float] = []

    for fallback_index, result in enumerate(results):
        payload = result.json if hasattr(result, "json") else result
        data = payload.get("res", payload)
        texts = _list(data.get("rec_texts"))
        scores = [float(score) for score in _list(data.get("rec_scores"))]
        boxes = _list(data.get("rec_boxes"))
        polygons = _list(data.get("rec_polys"))
        lines = []

        for index, text in enumerate(texts):
            confidence = scores[index] if index < len(scores) else None
            if confidence is not None:
                all_scores.append(confidence)
            lines.append({
                "line_id": f"p{fallback_index + 1}-l{index + 1}",
                "text": text,
                "confidence": confidence,
                "bbox": boxes[index] if index < len(boxes) else None,
                "polygon": polygons[index] if index < len(polygons) else None,
                "needs_review": confidence is None or confidence < 0.80,
            })

        page_scores = [line["confidence"] for line in lines if line["confidence"] is not None]
        pages.append({
            "page_number": int(data.get("page_index", fallback_index) or fallback_index) + 1,
            "text": "\n".join(text for text in texts if text),
            "mean_confidence": round(fmean(page_scores), 4) if page_scores else None,
            "lines": lines,
        })

    return {
        "schema_version": "1.0",
        "engine": {"name": "paddleocr", "model": model},
        "document": {"record_id": record_id, "page_count": len(pages)},
        "pages": pages,
        "full_text": "\n\n".join(page["text"] for page in pages if page["text"]),
        "metrics": {
            "mean_confidence": round(fmean(all_scores), 4) if all_scores else None,
            "low_confidence_lines": sum(line["needs_review"] for page in pages for line in page["lines"]),
            "total_lines": sum(len(page["lines"]) for page in pages),
        },
    }
