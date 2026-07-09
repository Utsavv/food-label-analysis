"""Deterministic functions exposed as ADK tools.

These are plain typed functions — ADK wraps them as FunctionTools when they
are attached to an agent. The same functions are called directly by the
deterministic pipeline, so agentic and scheduled flows share one code path.
"""
from typing import Any

from app.database import SessionLocal


def fetch_manufacturer_page(url: str, source_type: str = "manufacturer") -> dict[str, Any]:
    """Fetch a product page politely (robots.txt, rate limit) and extract label text.

    Args:
        url: The product page URL (mock:// URLs serve local demo fixtures).
        source_type: Adapter to use: manufacturer, retailer, mock, or manual.

    Returns:
        dict with ok, text, image_urls, error.
    """
    from app.services.scraping.base import get_adapter

    result = get_adapter(source_type).fetch(url)
    return {
        "ok": result.ok,
        "url": result.url,
        "text": result.text,
        "html_present": bool(result.html),
        "image_urls": result.image_urls,
        "error": result.error,
        "fetcher": result.fetcher,
    }


def extract_label_images(html: str, base_url: str) -> list[str]:
    """Find URLs of images on a product page that likely show the physical label."""
    from app.services.scraping.html_extractor import extract_label_images as _extract

    return _extract(html, base_url)


def run_ocr(image_path: str) -> dict[str, Any]:
    """Run OCR on a local label image using the configured provider."""
    from app.services.ocr.base import get_ocr_provider

    result = get_ocr_provider().extract_text(image_path)
    return {"text": result.text, "confidence": result.confidence,
            "provider": result.provider, "error": result.error}


def parse_label_text(raw_text: str) -> dict[str, Any]:
    """Deterministically parse raw label text into the structured label schema."""
    from app.services.extraction.label_parser import parse_label_text as _parse

    return _parse(raw_text).model_dump()


def normalize_nutrition(parsed_json: dict[str, Any]) -> dict[str, Any]:
    """Re-normalize nutrient names/units of a structured label dict in place."""
    from app.services.extraction.nutrition_normalizer import normalize_amount, normalize_nutrient_name

    for nutrient in parsed_json.get("nutrition", []):
        nutrient["name"] = normalize_nutrient_name(nutrient["name"])
        nutrient["amount"], nutrient["unit"] = normalize_amount(
            nutrient["name"], nutrient.get("amount"), nutrient.get("unit")
        )
    return parsed_json


def compare_label_versions(old_version_id: int, new_version_id: int) -> dict[str, Any]:
    """Compute the deterministic scored diff between two stored label versions."""
    from app.models import LabelVersion
    from app.services.comparison.label_diff import diff_labels
    from app.services.comparison.significance_scoring import score_diff

    with SessionLocal() as db:
        old = db.get(LabelVersion, old_version_id)
        new = db.get(LabelVersion, new_version_id)
        if not old or not new:
            return {"error": "label version not found"}
        category = new.product.category if new.product else None
        diff = diff_labels(old.structured_json, new.structured_json)
        return score_diff(diff, category)


def explain_ingredient(ingredient_name: str, category: str = "protein_powder") -> dict[str, Any]:
    """Explain a confusing ingredient in plain English (glossary or Gemini agent)."""
    from app.agents.ingredient_explainer_agent import run_ingredient_explainer

    return run_ingredient_explainer(ingredient_name, category)


def generate_change_analysis(diff_json: dict[str, Any], product_context: dict[str, Any]) -> dict[str, Any]:
    """Produce the plain-English change report for a scored diff."""
    from app.agents.change_analysis_agent import run_change_analysis

    return run_change_analysis(diff_json, product_context)


def save_label_version(product_id: int, structured_json: dict[str, Any],
                       raw_text: str, artifacts: list[str] | None = None) -> dict[str, Any]:
    """Persist a new label version (with normalized child rows) for a product."""
    from app.services.label_check import persist_label_version

    with SessionLocal() as db:
        version = persist_label_version(
            db, product_id=product_id, source_id=None, scrape_run_id=None,
            structured=structured_json, raw_text=raw_text, image_paths=artifacts or [],
        )
        db.commit()
        return {"label_version_id": version.id, "version_hash": version.version_hash,
                "version_number": version.version_number}


def create_comparison(old_version_id: int, new_version_id: int) -> dict[str, Any]:
    """Create and store a comparison record between two label versions."""
    from app.services.label_check import create_comparison_record

    with SessionLocal() as db:
        comparison = create_comparison_record(db, old_version_id, new_version_id)
        db.commit()
        if comparison is None:
            return {"error": "label version not found"}
        return {"comparison_id": comparison.id, "significance_score": comparison.significance_score}


ALL_TOOLS = [
    fetch_manufacturer_page,
    extract_label_images,
    run_ocr,
    parse_label_text,
    normalize_nutrition,
    compare_label_versions,
    explain_ingredient,
    generate_change_analysis,
    save_label_version,
    create_comparison,
]
