"""Label version history and detail endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIAnalysis, LabelVersion, Product
from app.schemas import AIAnalysisOut, LabelVersionOut, LabelVersionSummaryOut

router = APIRouter(tags=["label-versions"])


@router.get("/products/{product_id}/label-versions", response_model=list[LabelVersionSummaryOut])
def list_label_versions(product_id: int, db: Session = Depends(get_db)) -> list[LabelVersion]:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return list(db.scalars(
        select(LabelVersion).where(LabelVersion.product_id == product_id)
        .order_by(LabelVersion.version_number.desc())
    ).all())


@router.get("/label-versions/{version_id}", response_model=LabelVersionOut)
def get_label_version(version_id: int, db: Session = Depends(get_db)) -> LabelVersion:
    version = db.get(LabelVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Label version not found")
    return version


@router.get("/label-versions/{version_id}/analyses", response_model=list[AIAnalysisOut])
def get_version_analyses(version_id: int, db: Session = Depends(get_db)) -> list[AIAnalysis]:
    if db.get(LabelVersion, version_id) is None:
        raise HTTPException(status_code=404, detail="Label version not found")
    return list(db.scalars(
        select(AIAnalysis).where(AIAnalysis.label_version_id == version_id)
        .order_by(AIAnalysis.created_at.desc())
    ).all())
