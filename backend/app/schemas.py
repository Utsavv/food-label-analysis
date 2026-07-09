"""Pydantic API schemas and the canonical structured-label schema.

The structured label schema is shared by the deterministic parser and the
LabelExtractionAgent — both must produce `StructuredLabel`-shaped JSON.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# ---------------------------------------------------------------------------
# Structured label schema (canonical extraction output)
# ---------------------------------------------------------------------------

class FieldEvidence(BaseModel):
    """A value plus where on the label it came from, and how confident we are."""
    value: Any = None
    confidence: float = 0.0
    evidence: str | None = None  # verbatim source text; None => "not found on label/source"


class NutrientValue(BaseModel):
    name: str
    amount: float | None = None
    unit: str | None = None
    basis: str = "per_serving"  # per_serving | per_100g
    daily_value_percent: float | None = None
    confidence: float = 0.0
    evidence: str | None = None


class IngredientEntry(BaseModel):
    name_raw: str
    name_normalized: str
    position: int
    is_additive: bool = False
    is_sweetener: bool = False
    is_preservative: bool = False
    category: str | None = None


class AllergenEntry(BaseModel):
    name: str
    presence_type: str = "contains"  # contains | may_contain | traces
    evidence: str | None = None


class ClaimEntry(BaseModel):
    claim_text: str
    normalized_claim: str
    claim_type: str | None = None
    evidence: str | None = None


class StructuredLabel(BaseModel):
    """Canonical structured extraction of one label snapshot."""
    serving_size: FieldEvidence = Field(default_factory=FieldEvidence)
    servings_per_container: FieldEvidence = Field(default_factory=FieldEvidence)
    nutrition: list[NutrientValue] = Field(default_factory=list)
    ingredients: list[IngredientEntry] = Field(default_factory=list)
    allergens: list[AllergenEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    claims: list[ClaimEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    manufacturer_info: FieldEvidence = Field(default_factory=FieldEvidence)
    fssai_license: FieldEvidence = Field(default_factory=FieldEvidence)
    veg_status: FieldEvidence = Field(default_factory=FieldEvidence)  # vegetarian | non_vegetarian
    country_of_origin: FieldEvidence = Field(default_factory=FieldEvidence)
    overall_confidence: float = 0.0


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceCreate(BaseModel):
    source_type: str = "manufacturer"
    source_url: str
    is_active: bool = True
    scrape_frequency: str = "weekly"


class SourceOut(ORMModel):
    id: int
    product_id: int
    source_type: str
    source_url: str
    is_active: bool
    scrape_frequency: str
    last_checked_at: datetime | None
    created_at: datetime


class ProductCreate(BaseModel):
    brand: str
    name: str
    category: str  # e.g. "protein_powder", "protein_bar" — free-form for future categories
    country: str = "IN"
    notes: str | None = None
    source_url: HttpUrl | None = None  # convenience: create first manufacturer source inline
    source_type: str = "manufacturer"


class ProductOut(ORMModel):
    id: int
    brand: str
    name: str
    category: str
    country: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    sources: list[SourceOut] = []


class ProductSummaryOut(ProductOut):
    latest_version_id: int | None = None
    latest_version_at: datetime | None = None
    latest_significance: float | None = None


class NutritionItemOut(ORMModel):
    id: int
    nutrient_name: str
    amount: float | None
    unit: str | None
    per_serving_or_100g: str
    daily_value_percent: float | None
    raw_text: str | None


class IngredientOut(ORMModel):
    id: int
    ingredient_name_raw: str
    ingredient_name_normalized: str
    position: int
    category: str | None
    is_additive: bool
    is_sweetener: bool
    is_preservative: bool
    notes: str | None


class AllergenOut(ORMModel):
    id: int
    allergen_name: str
    presence_type: str
    raw_text: str | None


class CertificationOut(ORMModel):
    id: int
    certification_name: str
    status: str
    raw_text: str | None


class ClaimOut(ORMModel):
    id: int
    claim_text: str
    claim_type: str | None
    normalized_claim: str
    raw_text: str | None


class LabelVersionOut(ORMModel):
    id: int
    product_id: int
    source_id: int
    scrape_run_id: int | None
    version_number: int
    version_hash: str
    effective_detected_at: datetime
    raw_text: str
    original_image_paths: list | None
    structured_json: dict
    confidence_score: float
    created_at: datetime
    nutrition_items: list[NutritionItemOut] = []
    ingredients: list[IngredientOut] = []
    allergens: list[AllergenOut] = []
    certifications: list[CertificationOut] = []
    claims: list[ClaimOut] = []


class LabelVersionSummaryOut(ORMModel):
    id: int
    product_id: int
    version_number: int
    version_hash: str
    effective_detected_at: datetime
    confidence_score: float
    created_at: datetime


class AIAnalysisOut(ORMModel):
    id: int
    comparison_id: int | None
    label_version_id: int | None
    analysis_type: str
    prompt_version: str
    model_name: str
    analysis_json: dict
    plain_english_summary: str
    confidence_score: float
    created_at: datetime


class ComparisonOut(ORMModel):
    id: int
    product_id: int
    old_label_version_id: int
    new_label_version_id: int
    diff_json: dict
    significance_score: float
    created_at: datetime
    analyses: list[AIAnalysisOut] = []


class ScrapeRunOut(ORMModel):
    id: int
    product_id: int
    source_id: int
    status: str
    trigger: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    raw_text_excerpt: str | None
    artifact_path: str | None
    created_at: datetime


class CheckNowResult(BaseModel):
    run_id: int
    status: str
    new_version_created: bool
    label_version_id: int | None = None
    comparison_id: int | None = None
    significance_score: float | None = None
    message: str


class IngredientExplanation(BaseModel):
    ingredient_name: str
    plain_english_meaning: str
    common_use: str
    commonness: str
    health_context: str
    confidence: float
    model_name: str
    prompt_version: str


class DashboardStats(BaseModel):
    tracked_products: int
    changed_this_week: int
    high_significance_changes: int
    failed_runs_this_week: int
