"""Weekly scheduled label checks via APScheduler.

MVP-scale scheduler running inside the API process (ENABLE_SCHEDULER=true).
The job itself is a thin wrapper over the same deterministic pipeline used by
check-now, so moving to Cloud Scheduler / Cloud Run Jobs / Pub/Sub later only
means invoking `check_all_active_products` from a different entry point.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Product, ProductSource

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def check_all_active_products() -> dict[str, int]:
    """Run a label check for every active product with an active weekly source."""
    from app.services.label_check import run_label_check

    stats = {"checked": 0, "changed": 0, "failed": 0, "no_change": 0}
    with SessionLocal() as db:
        product_ids = db.scalars(
            select(Product.id)
            .join(ProductSource, ProductSource.product_id == Product.id)
            .where(Product.status == "active", ProductSource.is_active.is_(True),
                   ProductSource.scrape_frequency == "weekly")
            .distinct()
        ).all()

    for product_id in product_ids:
        with SessionLocal() as db:  # one transaction per product: a failure never blocks the rest
            try:
                result = run_label_check(db, product_id, trigger="scheduled")
                db.commit()
                stats["checked"] += 1
                if result.status == "failed":
                    stats["failed"] += 1
                elif result.new_version_created:
                    stats["changed"] += 1
                else:
                    stats["no_change"] += 1
            except Exception:
                db.rollback()
                stats["failed"] += 1
                logger.exception("Scheduled check failed for product %s", product_id)

    logger.info("Weekly check complete: %s", stats)
    return stats


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled (set ENABLE_SCHEDULER=true to enable)")
        return None
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        check_all_active_products,
        CronTrigger(day_of_week=settings.weekly_check_day, hour=settings.weekly_check_hour),
        id="weekly_label_check",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Weekly label-check scheduler started (%s %02d:00)",
                settings.weekly_check_day, settings.weekly_check_hour)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
