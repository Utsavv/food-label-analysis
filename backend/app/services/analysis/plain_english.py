"""Deterministic plain-English report generation and ingredient glossary.

Used directly in mock/demo mode (no LLM credentials) and as the factual
backbone that Gemini-backed agents rephrase. Facts come only from the
deterministic diff — never invented.
"""
from typing import Any

from app.services.analysis.risk_rules import DISCLAIMER, build_health_context

# Plain-English glossary for confusing ingredients common in protein products.
INGREDIENT_GLOSSARY: dict[str, dict[str, str]] = {
    "sucralose": {
        "meaning": "An artificial sweetener about 600 times sweeter than sugar, with almost no calories.",
        "common_use": "Used to make low-sugar products taste sweet without adding sugar or calories.",
        "commonness": "Very common in protein powders and 'sugar free' products in India.",
        "health_context": "Approved by FSSAI within limits. Fine for most people; some prefer to avoid "
                          "artificial sweeteners or report digestive discomfort at high intakes.",
    },
    "acesulfame potassium": {
        "meaning": "An artificial sweetener (also called Ace-K, INS 950), roughly 200 times sweeter than sugar.",
        "common_use": "Often blended with sucralose to give a more sugar-like sweetness.",
        "commonness": "Common in protein supplements and diet drinks.",
        "health_context": "FSSAI-approved within limits. Not a concern for most people at normal intakes.",
    },
    "steviol glycosides": {
        "meaning": "A plant-derived sweetener extracted from stevia leaves.",
        "common_use": "A 'natural' alternative to artificial sweeteners in low-sugar products.",
        "commonness": "Increasingly common in Indian protein and health-food brands.",
        "health_context": "Generally well tolerated; can have a mild bitter aftertaste. FSSAI-approved.",
    },
    "maltodextrin": {
        "meaning": "A processed carbohydrate made from starch that digests quickly, like sugar.",
        "common_use": "Used as a filler, thickener, or to add bulk and carbs cheaply.",
        "commonness": "Very common in mass-gainer and budget protein powders.",
        "health_context": "Raises blood sugar quickly despite not being labeled 'sugar' — relevant for "
                          "people managing blood sugar.",
    },
    "soy lecithin": {
        "meaning": "An emulsifier made from soybeans that helps powder mix smoothly in liquid.",
        "common_use": "Improves mixability ('instantized' protein powders).",
        "commonness": "Present in most whey protein powders.",
        "health_context": "Used in tiny amounts; contains soy, so it appears in allergen statements.",
    },
    "xanthan gum": {
        "meaning": "A thickener produced by fermenting sugars with a harmless bacterium.",
        "common_use": "Gives shakes and bars a thicker, smoother texture.",
        "commonness": "Common across packaged foods, not just protein products.",
        "health_context": "Safe for most people; very large amounts can cause bloating.",
    },
    "potassium sorbate": {
        "meaning": "A preservative that stops mould and yeast growth.",
        "common_use": "Extends shelf life of bars and moist products.",
        "commonness": "Common in packaged snacks and bars.",
        "health_context": "FSSAI-regulated and considered safe at permitted levels; some people prefer "
                          "preservative-free products.",
    },
    "whey protein concentrate": {
        "meaning": "Protein filtered from milk during cheese-making; typically 70-80% protein.",
        "common_use": "The main protein source in most protein powders.",
        "commonness": "The most common protein source in Indian protein supplements.",
        "health_context": "Contains lactose and milk allergens — relevant for lactose-intolerant or "
                          "milk-allergic users.",
    },
    "whey protein isolate": {
        "meaning": "A more filtered form of whey with ~90% protein and very little lactose or fat.",
        "common_use": "Premium protein source; easier on people with mild lactose intolerance.",
        "commonness": "Common in premium protein powders.",
        "health_context": "Still a milk product — not suitable for milk-allergic or vegan users.",
    },
    "isomalto-oligosaccharides": {
        "meaning": "A sweet-tasting fibre syrup (IMO) used to add sweetness and chewiness with fewer sugars.",
        "common_use": "Common binder/sweetener in 'low sugar' protein bars.",
        "commonness": "Very common in protein bars.",
        "health_context": "Partly digested like carbs, so 'fibre' on the label may act more like slow sugar; "
                          "large amounts can cause gas.",
    },
    "glycerin": {
        "meaning": "A sweet, syrupy substance (INS 422) that keeps bars soft and moist.",
        "common_use": "Humectant in protein and snack bars.",
        "commonness": "Very common in protein bars.",
        "health_context": "Safe at food levels; adds some calories, minimal blood-sugar impact.",
    },
}

_GENERIC_EXPLANATION = {
    "meaning": "not found on label/source — no verified plain-English entry for this ingredient yet.",
    "common_use": "not found on label/source",
    "commonness": "not found on label/source",
    "health_context": "No specific context available. Treat as a normal food ingredient unless the "
                      "allergen statement says otherwise.",
}


def explain_ingredient_deterministic(name: str, category: str | None = None) -> dict[str, Any]:
    key = name.strip().lower()
    entry = None
    for gloss_key, gloss in INGREDIENT_GLOSSARY.items():
        if gloss_key in key or key in gloss_key:
            entry = gloss
            break
    found = entry is not None
    entry = entry or _GENERIC_EXPLANATION
    return {
        "ingredient_name": name,
        "plain_english_meaning": entry["meaning"],
        "common_use": entry["common_use"],
        "commonness": entry["commonness"],
        "health_context": entry["health_context"],
        "confidence": 0.9 if found else 0.2,
        "disclaimer": DISCLAIMER,
    }


_LEVEL_PHRASES = {
    "very_high": "This is a significant change worth your attention.",
    "high": "This is a meaningful change.",
    "medium": "This is a moderate change.",
    "low": "This is a minor change.",
    "minimal": "This is a negligible change, likely rounding or formatting.",
}


def _who_should_care(scored_items: list[dict]) -> list[str]:
    audiences: set[str] = set()
    for item in scored_items:
        if item.get("significance", 0) < 35:
            continue
        t, f = item["type"], item.get("field", "")
        if t in ("allergen_added", "allergen_removed"):
            audiences.add("People with food allergies")
        if t == "veg_status_changed":
            audiences.add("Vegetarians and vegans")
        if f == "sodium":
            audiences.add("People monitoring sodium or blood pressure")
        if f in ("added_sugar", "total_sugar") or "sugar" in f:
            audiences.add("People monitoring sugar or calories")
        if f == "protein" or t == "serving_size_changed":
            audiences.add("Fitness users tracking protein and macros")
        if item.get("is_sweetener"):
            audiences.add("People avoiding artificial sweeteners")
        if t in ("certification_removed", "warning_added"):
            audiences.add("All buyers of this product")
    return sorted(audiences) or ["No specific group — changes are minor"]


def generate_change_report(scored_diff: dict[str, Any], product_context: dict[str, Any]) -> dict[str, Any]:
    """Build the structured 'what changed / why it matters / who should care' report."""
    items = scored_diff.get("items", [])
    overall = scored_diff.get("overall_score", 0.0)
    level = scored_diff.get("overall_level", "none")
    product_name = f"{product_context.get('brand', '')} {product_context.get('name', '')}".strip() or "This product"

    meaningful = [i for i in items if i.get("significance", 0) >= 35]
    minor = [i for i in items if 10 <= i.get("significance", 0) < 35]
    noise = [i for i in items if i.get("significance", 0) < 10]

    what_changed = [i["detail"] for i in sorted(items, key=lambda x: -x.get("significance", 0))]

    why_it_matters: list[str] = []
    for item in sorted(meaningful, key=lambda x: -x.get("significance", 0)):
        for ctx in _why_for_item(item):
            if ctx not in why_it_matters:
                why_it_matters.append(ctx)
    if not why_it_matters:
        why_it_matters.append("None of the detected changes meaningfully affect nutrition, safety disclosures, "
                              "or certifications.")

    if not items:
        summary = f"No changes detected on the latest label check for {product_name}."
    elif meaningful:
        top = sorted(meaningful, key=lambda x: -x.get("significance", 0))[:3]
        summary = (
            f"{product_name}: {len(items)} label change(s) detected. "
            f"Most important: " + "; ".join(t["detail"] for t in top) + ". "
            + _LEVEL_PHRASES.get(level, "")
        ).strip()
    else:
        summary = (
            f"{product_name}: {len(items)} small label change(s) detected, none significant. "
            + _LEVEL_PHRASES.get(level, "")
        ).strip()

    return {
        "summary": summary,
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "who_should_care": _who_should_care(items),
        "significance_score": overall,
        "significance_level": level,
        "meaningful_change_count": len(meaningful),
        "minor_change_count": len(minor),
        "noise_change_count": len(noise),
        "facts_vs_interpretation": {
            "facts": what_changed,
            "interpretation": why_it_matters,
        },
        "disclaimer": DISCLAIMER,
    }


def _why_for_item(item: dict) -> list[str]:
    """Reuse audience rules to phrase why a change matters."""
    from app.services.analysis.risk_rules import health_context_for_item

    return [c["statement"] for c in health_context_for_item(item)]


def generate_full_analysis(scored_diff: dict[str, Any], product_context: dict[str, Any]) -> dict[str, Any]:
    """Change report + health context in one payload (mock-mode analysis)."""
    report = generate_change_report(scored_diff, product_context)
    health = build_health_context(scored_diff)
    return {"change_report": report, "health_context": health}
