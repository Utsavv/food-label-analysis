"""Application configuration via environment variables (.env supported)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LabelWatch India"
    environment: str = "development"

    # SQLite works for quick local start; PostgreSQL is the primary target.
    database_url: str = "sqlite:///./labelwatch.db"

    # Where scraped HTML snapshots, label images and other evidence are stored.
    artifact_dir: str = "./artifacts"

    # AI provider: "mock" (no credentials needed) or "google" (Gemini via ADK).
    llm_provider: str = "mock"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # OCR provider: "mock", "tesseract" or "google_vision".
    ocr_provider: str = "mock"
    google_application_credentials: str = ""

    # Scraping etiquette
    scraper_user_agent: str = (
        "LabelWatchIndiaBot/0.1 (+https://github.com/utsavv/food-label-analysis; "
        "food label transparency research)"
    )
    scraper_min_delay_seconds: float = 2.0
    scraper_timeout_seconds: float = 30.0
    respect_robots_txt: bool = True

    # Scheduler
    enable_scheduler: bool = False
    weekly_check_day: str = "mon"
    weekly_check_hour: int = 6

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def artifact_path(self) -> Path:
        p = Path(self.artifact_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
