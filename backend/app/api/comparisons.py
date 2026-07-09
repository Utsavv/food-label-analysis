"""Comparison endpoints and the ingredient-explanation panel API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.ingredient_explainer_agent import run_ingredient_explainer
from app.database import get_db
from app.models import LabelComparison, Product
from app.schemas import ComparisonOut, IngredientExplanation

router = APIRouter(tags=["comparisons"])


@router.get("/products/{product_id}/comparisons", response_model=list[ComparisonOut])
def list_comparisons(product_id: int, db: Session = Depends(get_db)) -> list[LabelComparison]:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return list(db.scalars(
        select(LabelComparison).where(LabelComparison.product_id == product_id)
        .order_by(LabelComparison.created_at.desc())
    ).all())


@router.get("/comparisons/{comparison_id}", response_model=ComparisonOut)
def get_comparison(comparison_id: int, db: Session = Depends(get_db)) -> LabelComparison:
    comparison = db.get(LabelComparison, comparison_id)
    if comparison is None:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return comparison


@router.get("/ingredients/explain", response_model=IngredientExplanation)
def explain_ingredient(
    name: str = Query(..., min_length=2, max_length=200),
    category: str = Query(default="protein_powder"),
) -> IngredientExplanation:
    result = run_ingredient_explainer(name, category)
    return IngredientExplanation(
        ingredient_name=result["ingredient_name"],
        plain_english_meaning=result["plain_english_meaning"],
        common_use=result["common_use"],
        commonness=result["commonness"],
        health_context=result["health_context"],
        confidence=float(result.get("confidence", 0.0)),
        model_name=result.get("model_name", "unknown"),
        prompt_version=result.get("prompt_version", "unknown"),
    )
