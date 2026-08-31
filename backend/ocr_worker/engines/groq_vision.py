"""Groq vision-LLM transcription engine (OPT-IN, external API).

Same concept as a browser pdf.js + vision-model pipeline, but server-side:
the worker rasterises/normalises each page (documents.py) and sends one
image per page to Groq's multimodal chat API with a strict transcription
contract:

* one output line per written line (downstream line identity depends on it)
* [illegible] for unreadable words — the model must transcribe what is
  visible, never infer a medication or dose
* temperature 0, no reasoning — pure transcription

PRIVACY: page images leave this machine. This engine is disabled unless
OCR_ENGINE=groq AND GROQ_API_KEY is set. The key is read from the
environment only and is never logged or sent anywhere but api.groq.com.

The model returns plain text with no bounding boxes and no confidence
scores. Confidence is reported as None (never invented); lines containing
[illegible] are flagged needs_review, everything else is marked as
unscored LLM output for the reviewer to spot-check against the original.
"""
from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

from .base import EngineLine, EnginePage, OcrError

logger = logging.getLogger("docpilot.ocr.groq")

OCR_SYSTEM = """You are a document transcription engine for medical records.
Transcribe the page image exactly:
- One output line per written line on the page. Do not reflow or summarise.
- Keep labels, numbers, units and dates exactly as written (e.g. "Tab.", "1-0-1", "500 mg").
- Write [illegible] for any word you cannot read with certainty. NEVER guess a medication name or dosage.
- Do not interpret, correct, or complete clinical content. Transcribe only what is visible.
- Output the transcription only — no commentary, no markdown."""


class GroqVisionEngine:
    name = "groq-vision"

    def __init__(self, settings=None, poster=None):
        from app.config import get_settings

        self.settings = settings or get_settings()
        self.model = self.settings.groq_vision_model
        self._poster = poster  # test seam: callable(url, headers, json, timeout) -> response-like

    def warmup(self) -> None:
        if not self.settings.groq_api_key:
            raise OcrError(
                "model_init_failure",
                "OCR_ENGINE=groq but GROQ_API_KEY is not set; refusing to process documents",
                retryable=False,
            )

    # --- HTTP --------------------------------------------------------------

    def _post(self, payload: dict):
        import httpx

        url = f"{self.settings.groq_base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.groq_api_key}"}
        poster = self._poster or httpx.post
        waits = 0
        while True:
            try:
                resp = poster(url, headers=headers, json=payload, timeout=self.settings.groq_timeout_seconds)
            except Exception as exc:
                raise OcrError("transient", f"Groq request failed: {type(exc).__name__}", retryable=True) from exc
            status = getattr(resp, "status_code", 200)
            if status == 429 and waits < self.settings.groq_429_max_waits:
                waits += 1
                retry_after = float(getattr(resp, "headers", {}).get("retry-after", 2))
                logger.info("groq_rate_limited wait_s=%.0f attempt=%d", retry_after, waits)
                time.sleep(min(retry_after, 60))
                continue
            if status == 429:
                raise OcrError("transient", "Groq rate limit persisted", retryable=True)
            if status >= 400:
                raise OcrError("ocr_failure", f"Groq API returned HTTP {status}", retryable=status >= 500)
            return resp.json()

    # --- transcription -----------------------------------------------------

    def ocr_image(self, image_path: Path, page_number: int) -> EnginePage:
        self.warmup()
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        text = self._transcribe(image_b64, page_number, self.settings.groq_max_tokens)
        lines = [
            EngineLine(
                text=line,
                confidence=None,  # the model provides no confidence — never invent one
                needs_review="[illegible]" in line.lower(),
            )
            for line in text.splitlines()
            if line.strip()
        ]
        return EnginePage(page_number=page_number, lines=lines)

    def _transcribe(self, image_b64: str, page_number: int, max_tokens: int) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_completion_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": OCR_SYSTEM},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": f"Transcribe page {page_number}."},
                ]},
            ],
        }
        data = self._post(payload)
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        if choice.get("finish_reason") == "length" and max_tokens < self.settings.groq_max_tokens_retry:
            # page hit the output limit — retry this page once with the larger budget
            logger.info("groq_length_retry page=%d", page_number)
            return self._transcribe(image_b64, page_number, self.settings.groq_max_tokens_retry)
        return text
