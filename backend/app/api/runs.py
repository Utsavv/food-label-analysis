"""Scrape-run listing and dashboard statistics."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LabelComparison, Product, ScrapeRun
from app.schemas import DashboardStats, ScrapeRunOut

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[ScrapeRunOut])
def list_runs(
    status: str | None = Query(default=None),
    product_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> list[ScrapeRun]:
    stmt = select(ScrapeRun).order_by(ScrapeRun.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(ScrapeRun.status == status)
    if product_id:
        stmt = stmt.where(ScrapeRun.product_id == product_id)
    return list(db.scalars(stmt).all())


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    return DashboardStats(
        tracked_products=db.scalar(
            select(func.count(Product.id)).where(Product.status == "active")
        ) or 0,
        changed_this_week=db.scalar(
            select(func.count(func.distinct(LabelComparison.product_id)))
            .where(LabelComparison.created_at >= week_ago)
        ) or 0,
        high_significance_changes=db.scalar(
            select(func.count(LabelComparison.id))
            .where(LabelComparison.created_at >= week_ago,
                   LabelComparison.significance_score >= 60)
        ) or 0,
        failed_runs_this_week=db.scalar(
            select(func.count(ScrapeRun.id))
            .where(ScrapeRun.created_at >= week_ago, ScrapeRun.status == "failed")
        ) or 0,
    )
