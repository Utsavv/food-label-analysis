"""Normalized database models for LabelWatch India.

JSON columns use JSONB on PostgreSQL and plain JSON elsewhere (SQLite).
Categories are plain strings so new food categories need no schema change.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# JSONB on PostgreSQL, JSON elsewhere.
FlexJSON = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)  # e.g. protein_powder, protein_bar
    country: Mapped[str] = mapped_column(String(10), default="IN")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused | archived
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sources: Mapped[list["ProductSource"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    label_versions: Mapped[list["LabelVersion"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    scrape_runs: Mapped[list["ScrapeRun"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    comparisons: Mapped[list["LabelComparison"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductSource(Base):
    __tablename__ = "product_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    # manufacturer | retailer | uploaded_image | public_database | manual | mock
    source_type: Mapped[str] = mapped_column(String(50), default="manufacturer")
    source_url: Mapped[str] = mapped_column(String(2000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    scrape_frequency: Mapped[str] = mapped_column(String(20), default="weekly")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product: Mapped[Product] = relationship(back_populates="sources")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("product_sources.id"), index=True)
    # pending | running | success | no_change | failed
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual | scheduled | seed
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="scrape_runs")
    source: Mapped[ProductSource] = relationship()


class LabelVersion(Base):
    __tablename__ = "label_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("product_sources.id"))
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    version_hash: Mapped[str] = mapped_column(String(64), index=True)
    effective_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_text: Mapped[str] = mapped_column(Text)
    original_image_paths: Mapped[list | None] = mapped_column(FlexJSON, nullable=True)
    structured_json: Mapped[dict] = mapped_column(FlexJSON)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="label_versions")
    nutrition_items: Mapped[list["NutritionItem"]] = relationship(
        back_populates="label_version", cascade="all, delete-orphan"
    )
    ingredients: Mapped[list["Ingredient"]] = relationship(
        back_populates="label_version", cascade="all, delete-orphan"
    )
    allergens: Mapped[list["Allergen"]] = relationship(back_populates="label_version", cascade="all, delete-orphan")
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="label_version", cascade="all, delete-orphan"
    )
    claims: Mapped[list["LabelClaim"]] = relationship(back_populates="label_version", cascade="all, delete-orphan")


class NutritionItem(Base):
    __tablename__ = "nutrition_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_version_id: Mapped[int] = mapped_column(ForeignKey("label_versions.id"), index=True)
    nutrient_name: Mapped[str] = mapped_column(String(100), index=True)  # normalized key e.g. "sodium"
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    per_serving_or_100g: Mapped[str] = mapped_column(String(20), default="per_serving")
    daily_value_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    label_version: Mapped[LabelVersion] = relationship(back_populates="nutrition_items")


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_version_id: Mapped[int] = mapped_column(ForeignKey("label_versions.id"), index=True)
    ingredient_name_raw: Mapped[str] = mapped_column(String(300))
    ingredient_name_normalized: Mapped[str] = mapped_column(String(300), index=True)
    position: Mapped[int] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_additive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sweetener: Mapped[bool] = mapped_column(Boolean, default=False)
    is_preservative: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    label_version: Mapped[LabelVersion] = relationship(back_populates="ingredients")


class Allergen(Base):
    __tablename__ = "allergens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_version_id: Mapped[int] = mapped_column(ForeignKey("label_versions.id"), index=True)
    allergen_name: Mapped[str] = mapped_column(String(100), index=True)
    presence_type: Mapped[str] = mapped_column(String(30), default="contains")  # contains | may_contain | traces
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    label_version: Mapped[LabelVersion] = relationship(back_populates="allergens")


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_version_id: Mapped[int] = mapped_column(ForeignKey("label_versions.id"), index=True)
    certification_name: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(30), default="present")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    label_version: Mapped[LabelVersion] = relationship(back_populates="certifications")


class LabelClaim(Base):
    __tablename__ = "label_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_version_id: Mapped[int] = mapped_column(ForeignKey("label_versions.id"), index=True)
    claim_text: Mapped[str] = mapped_column(String(500))
    claim_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # nutrition | dietary | quality ...
    normalized_claim: Mapped[str] = mapped_column(String(200), index=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    label_version: Mapped[LabelVersion] = relationship(back_populates="claims")


class LabelComparison(Base):
    __tablename__ = "label_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    old_label_version_id: Mapped[int] = mapped_column(ForeignKey("label_versions.id"))
    new_label_version_id: Mapped[int] = mapped_column(ForeignKey("label_versions.id"))
    diff_json: Mapped[dict] = mapped_column(FlexJSON)
    significance_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="comparisons")
    old_version: Mapped[LabelVersion] = relationship(foreign_keys=[old_label_version_id])
    new_version: Mapped[LabelVersion] = relationship(foreign_keys=[new_label_version_id])
    analyses: Mapped[list["AIAnalysis"]] = relationship(back_populates="comparison")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comparison_id: Mapped[int | None] = mapped_column(ForeignKey("label_comparisons.id"), nullable=True, index=True)
    label_version_id: Mapped[int | None] = mapped_column(ForeignKey("label_versions.id"), nullable=True, index=True)
    # change_analysis | health_context | ingredient_explanation | extraction_assist
    analysis_type: Mapped[str] = mapped_column(String(50), index=True)
    prompt_version: Mapped[str] = mapped_column(String(20))
    model_name: Mapped[str] = mapped_column(String(100))
    analysis_json: Mapped[dict] = mapped_column(FlexJSON)
    plain_english_summary: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    comparison: Mapped[LabelComparison | None] = relationship(back_populates="analyses")
