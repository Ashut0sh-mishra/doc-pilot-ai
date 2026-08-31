"""Upload validation and page-by-page document preparation.

Responsibilities:
* validate the stored file (existence, size, extension, parseability)
* rasterise PDFs one page at a time (PyMuPDF) with a pixel budget, so a
  pathological PDF cannot exhaust worker memory
* normalise photos (EXIF orientation, RGB conversion, downscale)
* never touch the original upload — pages are written to a temp dir that
  is cleaned up by the caller

PyMuPDF only renders page content; PDF JavaScript/active content is never
executed.
"""
from __future__ import annotations

import math
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .engines.base import OcrError

PDF_RENDER_ZOOM = 2.0  # ~144 DPI; reduced automatically to fit the pixel budget


@dataclass
class PreparedPage:
    page_number: int
    image_path: Path | None  # None when the page failed to render
    error: str | None = None


def validate_record_file(record, settings) -> Path:
    """Validate the stored upload before any OCR work. Raises OcrError."""
    path = Path(settings.upload_dir).resolve() / f"{record.id}-{Path(record.filename).name}"
    if not path.exists():
        raise OcrError("invalid_input", "Uploaded file bytes are missing", retryable=False)

    size = path.stat().st_size
    if size == 0:
        raise OcrError("invalid_input", "Uploaded file is empty", retryable=False)
    if size > settings.max_upload_mb * 1024 * 1024:
        raise OcrError("too_large", f"File exceeds the {settings.max_upload_mb} MB limit", retryable=False)

    suffix = Path(record.filename).suffix.lower()
    if suffix not in settings.allowed_extension_set():
        raise OcrError("unsupported_format", f"Unsupported file type: {suffix or '(none)'}", retryable=False)
    return path


@contextmanager
def prepare_document(path: Path, settings) -> Iterator[tuple[int, Iterator[PreparedPage]]]:
    """Yield (total_pages, page iterator). Pages are prepared lazily, one at
    a time; the temp directory is removed when the context exits."""
    with tempfile.TemporaryDirectory(prefix="docpilot-ocr-") as work_dir:
        if path.suffix.lower() == ".pdf":
            yield _prepare_pdf(path, settings, Path(work_dir))
        else:
            yield _prepare_image(path, settings, Path(work_dir))


def _prepare_pdf(path: Path, settings, work_dir: Path):
    import pymupdf

    if path.read_bytes()[:5] != b"%PDF-":
        raise OcrError("corrupt_document", "File has a .pdf extension but is not a valid PDF", retryable=False)
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise OcrError("corrupt_document", f"Cannot open PDF: {exc}", retryable=False) from exc

    def pages() -> Iterator[PreparedPage]:
        try:
            for page_number in range(1, doc.page_count + 1):
                image_path = work_dir / f"page-{page_number}.png"
                try:
                    page = doc.load_page(page_number - 1)
                    zoom = _bounded_zoom(page.rect.width, page.rect.height, settings.max_page_pixels)
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                    pixmap.save(image_path)
                    del pixmap  # release page raster before the next page
                    yield PreparedPage(page_number=page_number, image_path=image_path)
                except Exception as exc:
                    yield PreparedPage(page_number=page_number, image_path=None, error=f"page render failed: {exc}")
                finally:
                    image_path.unlink(missing_ok=True)
        finally:
            doc.close()

    page_count = doc.page_count
    if page_count == 0:
        doc.close()
        raise OcrError("corrupt_document", "PDF contains no pages", retryable=False)
    if page_count > settings.max_pages:
        doc.close()
        raise OcrError("too_large", f"PDF has {page_count} pages; the limit is {settings.max_pages}", retryable=False)
    return page_count, pages()


def _prepare_image(path: Path, settings, work_dir: Path):
    from PIL import Image, ImageOps, UnidentifiedImageError

    def pages() -> Iterator[PreparedPage]:
        image_path = work_dir / "page-1.png"
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)  # honour camera orientation
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                if img.width * img.height > settings.max_page_pixels:
                    scale = math.sqrt(settings.max_page_pixels / (img.width * img.height))
                    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
                img.save(image_path, format="PNG")
            yield PreparedPage(page_number=1, image_path=image_path)
        except UnidentifiedImageError as exc:
            raise OcrError("corrupt_document", "File is not a readable image", retryable=False) from exc
        finally:
            image_path.unlink(missing_ok=True)

    return 1, pages()


def _bounded_zoom(width_pt: float, height_pt: float, max_page_pixels: int) -> float:
    zoom = PDF_RENDER_ZOOM
    if width_pt * height_pt * zoom * zoom > max_page_pixels:
        zoom = math.sqrt(max_page_pixels / (width_pt * height_pt))
    return max(zoom, 0.5)
