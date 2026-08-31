"""Embedded-text engine for digital (born-digital) PDFs.

Extracts the PDF text layer with PyMuPDF instead of running visual OCR.
This is deterministic extraction, not recognition: the text either exists
in the file or it does not, so per-line confidence is reported as None
(no recognition confidence exists) rather than an invented number, and
lines are marked trusted (needs_review=False). Scanned PDFs have no text
layer and produce empty pages — those documents need the paddle engine.
"""
from __future__ import annotations

from pathlib import Path

from .base import EngineLine, EnginePage, OcrError


class PdfTextEngine:
    name = "pymupdf-text"
    model = "embedded-text-layer"

    def warmup(self) -> None:
        try:
            import pymupdf  # noqa: F401
        except ImportError as exc:
            raise OcrError("model_init_failure", "PyMuPDF is not installed", retryable=False) from exc

    def ocr_image(self, image_path: Path, page_number: int) -> EnginePage:
        raise OcrError(
            "unsupported_format",
            "The pdftext engine only reads digital PDFs; photos/scans need the paddle engine",
            retryable=False,
        )

    def extract_pdf(self, pdf_path: Path, max_pages: int) -> list[EnginePage]:
        """Extract text page by page. A failing page is reported, not fatal."""
        import pymupdf

        try:
            doc = pymupdf.open(pdf_path)
        except Exception as exc:
            raise OcrError("corrupt_document", f"Cannot open PDF: {exc}", retryable=False) from exc
        pages: list[EnginePage] = []
        try:
            for page_number in range(1, min(doc.page_count, max_pages) + 1):
                try:
                    page = doc.load_page(page_number - 1)
                    words = page.get_text("text") or ""
                    lines = [
                        EngineLine(text=line, confidence=None, needs_review=False)
                        for line in words.splitlines()
                        if line.strip()
                    ]
                    pages.append(EnginePage(page_number=page_number, lines=lines))
                except Exception as exc:
                    pages.append(EnginePage(page_number=page_number, status="failed", error=f"text extraction failed: {exc}"))
        finally:
            doc.close()
        return pages
