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
    ocr_engine: str = "paddle"  # "paddle" (local scans/handwriting) | "pdftext" (digital PDFs) | "groq" (vision LLM, external)
    max_pages: int = 30
    max_page_pixels: int = 4_000_000  # pages/images are downscaled below this
    max_processing_seconds: int = 600
    ocr_max_retries: int = 3
    job_lease_seconds: int = 300  # processing job is reclaimed if the lease expires
    worker_poll_seconds: float = 2.0

    # --- Groq vision-LLM engine (OPT-IN, external API) ---
    # When OCR_ENGINE=groq, page images leave this machine and are sent to
    # Groq for transcription. Never enable for real patient data without a
    # signed DPA/BAA and explicit consent. Key comes from the environment,
    # never from the repo.
    groq_api_key: str | None = None
    groq_api_keys: str | None = None  # comma-separated pool, rotated on rate limits
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_vision_model: str = "qwen/qwen3.6-27b"  # multimodal; verified against the account's model list
    groq_text_model: str = "openai/gpt-oss-120b"
    groq_max_tokens: int = 1500          # per-page completion budget
    groq_max_tokens_retry: int = 4000    # budget when a page hits the length limit
    groq_timeout_seconds: int = 60
    groq_429_max_waits: int = 4          # retry-after honoured up to this many times
    # Optional structuring pass over the (already OCR'd) text. Produces
    # UNVERIFIED extraction JSON; never feeds back into the OCR text.
    groq_extraction_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def groq_key_list(self) -> list[str]:
        keys = self.groq_api_keys or self.groq_api_key or ""
        return [k.strip() for k in keys.split(",") if k.strip()]

    def allowed_extension_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()}

    def allowed_content_type_set(self) -> set[str]:
        return {ct.strip().lower() for ct in self.allowed_content_types.split(",") if ct.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
