"""Optional LLM structuring pass ("reasoning") over OCR text.

This is NOT part of OCR. It runs only after transcription, only when
GROQ_EXTRACTION_ENABLED=true, and its output is stored separately under
result_json["extraction"] with unverified=true. It must never modify
raw_text, never decide clinical truth, and never fail the OCR job —
extraction errors are logged and skipped.

Like the vision engine, this sends document text to an external API
(Groq). Same privacy rules apply: opt-in only.
"""
from __future__ import annotations

import json
import logging

from .engines.base import OcrError

logger = logging.getLogger("docpilot.ocr.extraction")

EXTRACTION_SYSTEM = """You structure transcribed medical-record text into JSON.
Rules:
- Use ONLY information present in the transcription. Never infer, complete, or correct.
- If the transcription says [illegible] or is unclear, carry that uncertainty into the output — do not guess.
- This output is unverified decision support for a human reviewer, not medical advice.
Return strict JSON with this shape (omit keys with no evidence):
{
  "medications": [{"name": str, "dose": str|null, "frequency": str|null, "uncertain": bool}],
  "measurements": [{"name": str, "value": str, "unit": str|null, "date": str|null, "uncertain": bool}],
  "problems": [str],
  "dates": [str],
  "uncertain_spans": [str]
}"""

MAX_INPUT_CHARS = 12_000


def extract_clinical_structure(raw_text: str, settings, poster=None) -> dict | None:
    """Return unverified structured extraction, or None on any failure."""
    keys = settings.groq_key_list()
    if not keys:
        return None
    import httpx

    payload = {
        "model": settings.groq_text_model,
        "temperature": 0,
        "max_completion_tokens": 2000,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": raw_text[:MAX_INPUT_CHARS]},
        ],
    }
    url = f"{settings.groq_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {keys[0]}"}
    try:
        resp = (poster or httpx.post)(url, headers=headers, json=payload, timeout=settings.groq_timeout_seconds)
        if getattr(resp, "status_code", 200) >= 400:
            raise OcrError("transient", f"extraction HTTP {resp.status_code}", retryable=True)
        content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content") or ""
        data = json.loads(content)
    except Exception as exc:
        logger.warning("extraction_skipped reason=%s", type(exc).__name__)
        return None
    return {
        "unverified": True,
        "engine": "groq",
        "model": settings.groq_text_model,
        "notice": "AI-generated structure from OCR text. Not verified clinical data — confirm against the original document.",
        "data": data,
    }
