"""Normalise engine output into the DocPilot OCR schema.

Schema 1.1 retains everything 1.0 had (line IDs, per-line confidence,
boxes, polygons, review flags) and adds per-page status so one failed
page never discards the pages that succeeded. Confidence is reported
exactly as the engine provides it — None means "no confidence signal",
never an invented number.
"""
from __future__ import annotations

from statistics import fmean
from typing import Any

from .engines.base import EnginePage

CONFIDENCE_REVIEW_THRESHOLD = 0.80
SCHEMA_VERSION = "1.1"


def _list(value: Any) -> list:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def line_needs_review(confidence: float | None, explicit: bool | None = None) -> bool:
    if explicit is not None:
        return explicit
    # No confidence signal means a human should look at the line.
    return confidence is None or confidence < CONFIDENCE_REVIEW_THRESHOLD


def assemble_result(record_id: str, engine_name: str, model: str, pages: list[EnginePage]) -> dict:
    """Build the schema-1.1 document from per-page engine results."""
    out_pages = []
    all_scores: list[float] = []

    for page in pages:
        lines = []
        for index, line in enumerate(page.lines):
            if line.confidence is not None:
                all_scores.append(line.confidence)
            lines.append({
                "line_id": f"p{page.page_number}-l{index + 1}",
                "text": line.text,
                "confidence": line.confidence,
                "bbox": line.bbox,
                "polygon": line.polygon,
                "needs_review": line_needs_review(line.confidence, line.needs_review),
            })
        page_scores = [l.confidence for l in page.lines if l.confidence is not None]
        out_pages.append({
            "page_number": page.page_number,
            "status": page.status,
            "error": page.error,
            "text": "\n".join(l.text for l in page.lines if l.text),
            "mean_confidence": round(fmean(page_scores), 4) if page_scores else None,
            "lines": lines,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "engine": {"name": engine_name, "model": model},
        "document": {"record_id": record_id, "page_count": len(out_pages)},
        "pages": out_pages,
        "full_text": "\n\n".join(p["text"] for p in out_pages if p["text"]),
        "metrics": {
            "mean_confidence": round(fmean(all_scores), 4) if all_scores else None,
            "low_confidence_lines": sum(l["needs_review"] for p in out_pages for l in p["lines"]),
            "total_lines": sum(len(p["lines"]) for p in out_pages),
            "failed_pages": sum(1 for p in out_pages if p["status"] == "failed"),
        },
    }


def normalize_paddle_results(results: list[Any], record_id: str, model: str = "PP-OCRv5") -> dict:
    """Convert raw PaddleOCR Result objects/dicts to the OCR schema.

    Kept for backwards compatibility; the worker now goes through
    engines.paddle + assemble_result instead.
    """
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
                "needs_review": confidence is None or confidence < CONFIDENCE_REVIEW_THRESHOLD,
            })

        page_scores = [line["confidence"] for line in lines if line["confidence"] is not None]
        pages.append({
            "page_number": int(data.get("page_index", fallback_index) or fallback_index) + 1,
            "status": "ok",
            "error": None,
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
