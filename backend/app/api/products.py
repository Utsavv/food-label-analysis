"""Product CRUD, sources, and the check-now trigger."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LabelComparison, LabelVersion, Product, ProductSource
from app.schemas import (
    CheckNowResult,
    ProductCreate,
    ProductOut,
    ProductSummaryOut,
    SourceCreate,
    SourceOut,
)
from app.services.label_check import run_label_check

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(
        brand=payload.brand, name=payload.name, category=payload.category,
        country=payload.country, notes=payload.notes,
    )
    db.add(product)
    db.flush()
    if payload.source_url:
        db.add(ProductSource(product_id=product.id, source_type=payload.source_type,
                             source_url=str(payload.source_url)))
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductSummaryOut])
def list_products(
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProductSummaryOut]:
    stmt = select(Product).order_by(Product.id)
    if category:
        stmt = stmt.where(Product.category == category)
    if status:
        stmt = stmt.where(Product.status == status)
    products = db.scalars(stmt).all()

    out: list[ProductSummaryOut] = []
    for product in products:
        latest = db.scalars(
            select(LabelVersion).where(LabelVersion.product_id == product.id)
            .order_by(LabelVersion.version_number.desc()).limit(1)
        ).first()
        latest_comp = db.scalars(
            select(LabelComparison).where(LabelComparison.product_id == product.id)
            .order_by(LabelComparison.created_at.desc()).limit(1)
        ).first()
        summary = ProductSummaryOut.model_validate(product)
        summary.latest_version_id = latest.id if latest else None
        summary.latest_version_at = latest.effective_detected_at if latest else None
        summary.latest_significance = latest_comp.significance_score if latest_comp else None
        out.append(summary)
    return out


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/{product_id}/sources", response_model=SourceOut, status_code=201)
def add_source(product_id: int, payload: SourceCreate, db: Session = Depends(get_db)) -> ProductSource:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    source = ProductSource(product_id=product_id, **payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.post("/{product_id}/check-now", response_model=CheckNowResult)
def check_now(product_id: int, db: Session = Depends(get_db)) -> CheckNowResult:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        result = run_label_check(db, product_id, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/{product_id}/dashboard-week")
def product_week_activity(product_id: int, db: Session = Depends(get_db)) -> dict:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    changes = db.scalar(
        select(func.count(LabelComparison.id))
        .where(LabelComparison.product_id == product_id, LabelComparison.created_at >= week_ago)
    )
    return {"product_id": product_id, "comparisons_this_week": changes or 0}
