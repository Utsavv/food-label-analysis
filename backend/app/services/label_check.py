"""Deterministic label-check pipeline.

fetch -> (OCR) -> extract -> hash/version -> diff -> score -> AI analyses.

This is the single code path used by the API's check-now endpoint, the weekly
scheduler, and the seed script. ADK agents are invoked only for the reasoning
steps (extraction assist, change analysis, health context); control flow is
plain code, per the architecture principle.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    AIAnalysis,
    Allergen,
    Certification,
    Ingredient,
    LabelClaim,
    LabelComparison,
    LabelVersion,
    NutritionItem,
    Product,
    ProductSource,
    ScrapeRun,
)
from app.schemas import CheckNowResult, StructuredLabel
from app.services.comparison.label_diff import compute_version_hash, diff_labels
from app.services.comparison.significance_scoring import score_diff
from app.services.scraping.base import get_adapter
from app.services.storage.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def latest_version(db: Session, product_id: int) -> LabelVersion | None:
    return db.scalars(
        select(LabelVersion)
        .where(LabelVersion.product_id == product_id)
        .order_by(LabelVersion.version_number.desc(), LabelVersion.id.desc())
    ).first()


def persist_label_version(
    db: Session,
    product_id: int,
    source_id: int | None,
    scrape_run_id: int | None,
    structured: dict,
    raw_text: str,
    image_paths: list[str],
    confidence: float | None = None,
) -> LabelVersion:
    """Store a label version plus its normalized child rows."""
    label = StructuredLabel.model_validate(structured)
    previous = latest_version(db, product_id)

    version = LabelVersion(
        product_id=product_id,
        source_id=source_id if source_id is not None else (previous.source_id if previous else 0),
        scrape_run_id=scrape_run_id,
        version_number=(previous.version_number + 1) if previous else 1,
        version_hash=compute_version_hash(label.model_dump()),
        raw_text=raw_text,
        original_image_paths=image_paths,
        structured_json=label.model_dump(),
        confidence_score=confidence if confidence is not None else label.overall_confidence,
    )
    db.add(version)
    db.flush()

    for n in label.nutrition:
        db.add(NutritionItem(
            label_version_id=version.id, nutrient_name=n.name, amount=n.amount, unit=n.unit,
            per_serving_or_100g=n.basis, daily_value_percent=n.daily_value_percent, raw_text=n.evidence,
        ))
    for ing in label.ingredients:
        db.add(Ingredient(
            label_version_id=version.id, ingredient_name_raw=ing.name_raw,
            ingredient_name_normalized=ing.name_normalized, position=ing.position,
            category=ing.category, is_additive=ing.is_additive, is_sweetener=ing.is_sweetener,
            is_preservative=ing.is_preservative,
        ))
    for a in label.allergens:
        db.add(Allergen(label_version_id=version.id, allergen_name=a.name,
                        presence_type=a.presence_type, raw_text=a.evidence))
    for c in label.certifications:
        db.add(Certification(label_version_id=version.id, certification_name=c, status="present"))
    for cl in label.claims:
        db.add(LabelClaim(label_version_id=version.id, claim_text=cl.claim_text,
                          claim_type=cl.claim_type, normalized_claim=cl.normalized_claim,
                          raw_text=cl.evidence))
    db.flush()
    return version


def create_comparison_record(db: Session, old_version_id: int, new_version_id: int) -> LabelComparison | None:
    old = db.get(LabelVersion, old_version_id)
    new = db.get(LabelVersion, new_version_id)
    if old is None or new is None:
        return None
    product = db.get(Product, new.product_id)
    diff = diff_labels(old.structured_json, new.structured_json)
    scored = score_diff(diff, product.category if product else None)
    comparison = LabelComparison(
        product_id=new.product_id,
        old_label_version_id=old_version_id,
        new_label_version_id=new_version_id,
        diff_json=scored,
        significance_score=scored["overall_score"],
    )
    db.add(comparison)
    db.flush()
    return comparison


def _store_analysis(db: Session, *, comparison_id: int | None, label_version_id: int | None,
                    analysis_type: str, payload: dict, summary: str) -> AIAnalysis:
    """Persist an AI output with full provenance (model, prompt version, confidence)."""
    analysis = AIAnalysis(
        comparison_id=comparison_id,
        label_version_id=label_version_id,
        analysis_type=analysis_type,
        prompt_version=payload.get("prompt_version", "unknown"),
        model_name=payload.get("model_name", "unknown"),
        analysis_json=payload,
        plain_english_summary=summary,
        confidence_score=float(payload.get("confidence", 0.8) or 0.8),
    )
    db.add(analysis)
    db.flush()
    return analysis


def run_analyses_for_comparison(db: Session, comparison: LabelComparison) -> None:
    """Run ChangeAnalysisAgent + HealthContextAgent on a comparison and store outputs."""
    from app.agents.change_analysis_agent import run_change_analysis
    from app.agents.health_context_agent import run_health_context

    product = db.get(Product, comparison.product_id)
    context = {
        "brand": product.brand if product else "",
        "name": product.name if product else "",
        "category": product.category if product else "",
        "country": product.country if product else "IN",
    }

    change = run_change_analysis(comparison.diff_json, context)
    _store_analysis(
        db, comparison_id=comparison.id, label_version_id=comparison.new_label_version_id,
        analysis_type="change_analysis", payload=change, summary=change.get("summary", ""),
    )

    health = run_health_context(comparison.diff_json, context)
    health_summary = " ".join(
        c["statement"] for c in health.get("contexts", [])[:3]
    ) or "No audience-specific health context for these changes."
    _store_analysis(
        db, comparison_id=comparison.id, label_version_id=comparison.new_label_version_id,
        analysis_type="health_context", payload=health, summary=health_summary,
    )


def run_label_check(db: Session, product_id: int, source_id: int | None = None,
                    trigger: str = "manual") -> CheckNowResult:
    """Full check for one product: scrape, extract, version, compare, analyze."""
    product = db.get(Product, product_id)
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    source: ProductSource | None
    if source_id is not None:
        source = db.get(ProductSource, source_id)
    else:
        source = db.scalars(
            select(ProductSource)
            .where(ProductSource.product_id == product_id, ProductSource.is_active.is_(True))
            .order_by(ProductSource.id)
        ).first()
    if source is None:
        raise ValueError(f"No active source configured for product {product_id}")

    run = ScrapeRun(product_id=product_id, source_id=source.id, status="running",
                    trigger=trigger, started_at=_utcnow())
    db.add(run)
    db.flush()

    settings = get_settings()
    store = ArtifactStore()

    try:
        adapter = get_adapter(source.source_type)
        fetch = adapter.fetch(source.source_url)
        source.last_checked_at = _utcnow()

        if not fetch.ok or not (fetch.text or fetch.html):
            run.status = "failed"
            run.error_message = fetch.error or "No content returned"
            run.completed_at = _utcnow()
            db.flush()
            return CheckNowResult(run_id=run.id, status="failed", new_version_created=False,
                                  message=f"Scrape failed: {run.error_message}")

        raw_text = fetch.text or ""
        artifact_dir = store.save_snapshot(product_id, run.id, fetch.html, raw_text)
        run.artifact_path = artifact_dir
        image_paths = store.save_images(product_id, run.id, fetch.image_urls,
                                        settings.scraper_user_agent) if fetch.image_urls else []

        # OCR path: page text too thin but label images exist
        if len(raw_text.strip()) < 80 and image_paths:
            from app.services.ocr.base import get_ocr_provider

            ocr = get_ocr_provider()
            ocr_texts = []
            for path in image_paths:
                result = ocr.extract_text(path)
                if result.text:
                    ocr_texts.append(result.text)
                elif result.error:
                    logger.info("OCR skipped for %s: %s", path, result.error)
            if ocr_texts:
                raw_text = raw_text + "\n" + "\n".join(ocr_texts)

        if len(raw_text.strip()) < 40:
            run.status = "failed"
            run.error_message = "Not enough label text extracted from source (page or OCR)"
            run.completed_at = _utcnow()
            db.flush()
            return CheckNowResult(run_id=run.id, status="failed", new_version_created=False,
                                  message=run.error_message)

        run.raw_text_excerpt = raw_text[:1000]

        # Extraction (deterministic parser, LLM assist on low confidence)
        from app.agents.label_extraction_agent import run_extraction

        label, extraction_model, prompt_version = run_extraction(raw_text)
        structured = label.model_dump()
        new_hash = compute_version_hash(structured)

        previous = latest_version(db, product_id)
        if previous and previous.version_hash == new_hash:
            run.status = "no_change"
            run.completed_at = _utcnow()
            db.flush()
            return CheckNowResult(
                run_id=run.id, status="no_change", new_version_created=False,
                label_version_id=previous.id,
                message="Label unchanged since last check.",
            )

        version = persist_label_version(
            db, product_id=product_id, source_id=source.id, scrape_run_id=run.id,
            structured=structured, raw_text=raw_text, image_paths=image_paths,
        )
        if extraction_model != "deterministic-parser":
            _store_analysis(
                db, comparison_id=None, label_version_id=version.id,
                analysis_type="extraction_assist",
                payload={"model_name": extraction_model, "prompt_version": prompt_version,
                         "confidence": label.overall_confidence},
                summary="LLM-assisted extraction of low-confidence label text.",
            )

        comparison_id = None
        significance = None
        if previous is not None:
            comparison = create_comparison_record(db, previous.id, version.id)
            if comparison:
                run_analyses_for_comparison(db, comparison)
                comparison_id = comparison.id
                significance = comparison.significance_score

        run.status = "success"
        run.completed_at = _utcnow()
        db.flush()

        message = (
            f"New label version v{version.version_number} stored."
            + (f" {len(version.structured_json.get('nutrition', []))} nutrients extracted." if version else "")
            + (f" Changes detected — significance {significance}/100." if comparison_id else
               " First version captured; nothing to compare yet." if previous is None else "")
        )
        return CheckNowResult(
            run_id=run.id, status="success", new_version_created=True,
            label_version_id=version.id, comparison_id=comparison_id,
            significance_score=significance, message=message.strip(),
        )
    except Exception as exc:
        logger.exception("Label check failed for product %s", product_id)
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = _utcnow()
        db.flush()
        return CheckNowResult(run_id=run.id, status="failed", new_version_created=False,
                              message=f"Label check failed: {exc}")
