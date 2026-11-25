"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "UNIFORGE AI"
    app_env: str = "development"
    app_debug: bool = True
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Security & Auth
    secret_key: str = Field(
        default="uniforge-dev-secret-key-replace-in-production-64-bytes-minimum-entropy"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    csrf_secret: str = "uniforge-dev-csrf-secret-change-in-prod"
    encryption_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./uniforge_dev.db"
    database_url_sync: str = "sqlite:///./uniforge_dev.db"
    db_echo: bool = False

    # Redis & Jobs
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    use_inline_job_runner: bool = True

    # Storage
    storage_backend: str = "local"  # local | s3
    local_storage_path: str = "./storage_data"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket_name: str = "uniforge-assets"
    s3_region: str = "us-east-1"
    max_upload_size_mb: int = 50
    default_user_storage_quota_mb: int = 500

    # AI Language Intelligence (GPT-6 Astra Primary + OpenAI-Compatible + Ollama)
    ai_primary_provider: str = "openai_astra"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_astra_model: str = "gpt-6-astra"
    openai_astra_reasoning_effort: str = "medium"

    custom_ai_base_url: str = ""
    custom_ai_api_key: str = ""
    custom_ai_model: str = ""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # AI Image Generation
    image_provider: str = "none"  # openai | stability | huggingface | comfyui | none
    image_api_key: str = ""
    image_base_url: str = ""
    image_model: str = "gpt-image-1"

    # AI Video Generation & FFmpeg Assembly
    video_provider: str = "local_ffmpeg"  # runway | replicate | local_ffmpeg | none
    video_api_key: str = ""
    video_base_url: str = ""
    ffmpeg_binary: str = "ffmpeg"

    # Research APIs (Free public academic discovery)
    crossref_mailto: str = "research@uniforge.ai"
    openalex_mailto: str = "research@uniforge.ai"
    semantic_scholar_api_key: str = ""

    # Fair-Use Limits (Free Academic Platform)
    fair_use_ai_requests_per_day: int = 100
    fair_use_images_per_day: int = 20
    fair_use_videos_per_day: int = 5
    fair_use_exports_per_day: int = 50
    rate_limit_requests_per_minute: int = 120

    # SMTP (optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@uniforge.ai"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def storage_root(self) -> Path:
        path = Path(self.local_storage_path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def default_quota_bytes(self) -> int:
        return self.default_user_storage_quota_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
