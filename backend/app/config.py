from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DocPilot API"
    app_env: str = "development"
    database_url: str = "sqlite:///./docpilot.db"
    storage_bucket: str = "docpilot-records"
    storage_region: str = "ap-south-1"
    upload_dir: str = "./uploads"

    # --- Upload validation ---
    max_upload_mb: int = 20
    # Extensions/MIME types the OCR pipeline can actually process.
    allowed_extensions: str = ".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
    allowed_content_types: str = "application/pdf,image/png,image/jpeg,image/webp,image/bmp,image/tiff"

    # --- OCR pipeline ---
    ocr_engine: str = "paddle"  # "paddle" (scans/handwriting) or "pdftext" (digital PDFs only)
    max_pages: int = 30
    max_page_pixels: int = 4_000_000  # pages/images are downscaled below this
    max_processing_seconds: int = 600
    ocr_max_retries: int = 3
    job_lease_seconds: int = 300  # processing job is reclaimed if the lease expires
    worker_poll_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def allowed_extension_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()}

    def allowed_content_type_set(self) -> set[str]:
        return {ct.strip().lower() for ct in self.allowed_content_types.split(",") if ct.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
