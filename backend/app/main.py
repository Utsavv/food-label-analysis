"""LabelWatch India API entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import comparisons, label_versions, products, runs
from app.config import get_settings
from app.database import init_db
from app.services.scheduler.weekly_checker import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Register source adapters
    import app.services.scraping.manufacturer_scraper  # noqa: F401

    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Agentic monitoring of Indian packaged-food labels. "
        "Informational only — not medical advice."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(label_versions.router)
app.include_router(comparisons.router)
app.include_router(runs.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_provider": settings.llm_provider,
        "ocr_provider": settings.ocr_provider,
        "scheduler_enabled": settings.enable_scheduler,
    }
