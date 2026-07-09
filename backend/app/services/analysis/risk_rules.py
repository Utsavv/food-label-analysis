"""Deterministic, audience-aware health-context rules for label changes.

These rules produce realistic consumer context — direct but not alarmist.
They power the mock HealthContextAgent and act as guardrails/reference for
the Gemini-backed agent. Nothing here is medical advice.
"""
from typing import Any

AUDIENCES = [
    "general_consumers",
    "fitness_users",
    "sugar_watchers",
    "sodium_hypertension_watchers",
    "allergy_sufferers",
    "vegetarians_vegans",
    "caffeine_sweetener_sensitive",
]

DISCLAIMER = (
    "This analysis is informational and not medical advice. Always check the actual "
    "product label and consult a qualified professional for medical or allergy-related decisions."
)


def _fmt_change(item: dict) -> str:
    unit = item.get("unit") or ""
    return f"{item.get('old_value')} {unit} to {item.get('new_value')} {unit}".replace("  ", " ").strip()


def health_context_for_item(item: dict[str, Any]) -> list[dict[str, str]]:
    """Return audience-tagged context statements for one scored diff item."""
    dtype = item["type"]
    field = item.get("field", "")
    sig = item.get("significance", 0)
    contexts: list[dict[str, str]] = []

    def add(audience: str, statement: str, evidence_level: str = "label_comparison") -> None:
        contexts.append({"audience": audience, "statement": statement, "evidence_level": evidence_level})

    if dtype == "allergen_added":
        add("allergy_sufferers",
            f"The label now discloses {field} ({item.get('presence_type', 'contains').replace('_', ' ')}). "
            f"If you are allergic to {field}, do not consume this product without checking the physical label.")
        add("general_consumers",
            f"A new allergen disclosure ({field}) usually reflects a recipe change or a shared "
            "manufacturing line. Most people without this allergy are not affected.")

    elif dtype == "allergen_removed":
        add("allergy_sufferers",
            f"The {field} disclosure was removed. This could mean a formulation change or just a labeling "
            f"update — if you are allergic to {field}, verify with the manufacturer before assuming it is gone.")

    elif dtype == "nutrient_amount_changed":
        pct = item.get("percent_change")
        direction = "increased" if (pct or 0) > 0 else "decreased"
        if field == "sodium" and direction == "increased" and sig >= 35:
            add("sodium_hypertension_watchers",
                f"Sodium {direction} from {_fmt_change(item)}. This may be a concern for people with "
                "hypertension if they consume this product regularly.")
            add("general_consumers",
                "For most healthy adults, this sodium change is unlikely to matter at typical serving sizes.")
        elif field in ("added_sugar", "total_sugar") and direction == "increased" and sig >= 35:
            add("sugar_watchers",
                f"{field.replace('_', ' ').title()} {direction} from {_fmt_change(item)}. This matters for "
                "people managing blood sugar or total calorie intake.")
            add("fitness_users",
                "Extra sugar adds calories without protein. Factor it into your daily intake if you track macros.")
        elif field == "protein" and direction == "decreased" and sig >= 35:
            add("fitness_users",
                f"Protein {direction} from {_fmt_change(item)}. If you buy this product for protein content, "
                "you now get less per serving — compare cost per gram of protein with alternatives.")
            add("general_consumers",
                "Lower protein per serving means the product is less concentrated than before.")
        elif field == "trans_fat" and direction == "increased":
            add("general_consumers",
                f"Trans fat {direction} from {_fmt_change(item)}. Health bodies including FSSAI recommend "
                "keeping trans fat intake as low as possible.")
        elif field == "saturated_fat" and direction == "increased" and sig >= 35:
            add("general_consumers",
                f"Saturated fat {direction} from {_fmt_change(item)}. Relevant if you are watching "
                "cholesterol or heart health, less important as an occasional intake.")
        elif sig >= 35:
            add("general_consumers",
                f"{field.replace('_', ' ').title()} {direction} from {_fmt_change(item)}.")

    elif dtype == "ingredient_added":
        if item.get("is_sweetener"):
            add("caffeine_sweetener_sensitive",
                f"An artificial/intense sweetener ({field}) was added. These are approved by FSSAI at permitted "
                "levels, but some people prefer to avoid them or notice digestive effects at high intakes.")
            add("sugar_watchers",
                f"The sweetener {field} adds sweetness without sugar. Total sugar may drop while sweetness stays.")
        elif item.get("is_preservative"):
            add("general_consumers",
                f"A preservative ({field}) was added. Preservatives used in India are FSSAI-regulated; "
                "this mostly matters if you specifically avoid them.")
        elif item.get("is_additive"):
            add("general_consumers",
                f"A new additive ({field}) appears on the label. Additives are FSSAI-regulated; the practical "
                "impact for most consumers is small.")

    elif dtype == "veg_status_changed":
        add("vegetarians_vegans",
            f"The veg/non-veg mark changed from {item.get('old_value')} to {item.get('new_value')}. "
            "Check the physical pack before buying if you follow a vegetarian or vegan diet.")

    elif dtype == "certification_removed":
        add("general_consumers",
            f"The {field} certification is no longer shown. This may mean the certification lapsed, was dropped, "
            "or the website was updated — it does not automatically mean quality fell, but it removes third-party assurance.")

    elif dtype == "claim_removed":
        if "sugar" in field:
            add("sugar_watchers",
                f"The '{field.replace('_', ' ')}' claim was removed. Check the added-sugar line in the nutrition "
                "table — the recipe may now contain added sugar.")
        else:
            add("general_consumers",
                f"The '{field.replace('_', ' ')}' claim was removed, which can signal a recipe or compliance change.")

    elif dtype == "serving_size_changed":
        add("fitness_users",
            "Serving size changed. Per-serving numbers are no longer directly comparable with the old label — "
            "compare per 100 g values instead.")
        add("general_consumers",
            "A serving-size change can make nutrition numbers look better or worse without any recipe change.")

    elif dtype == "warning_added":
        add("general_consumers", f"A new warning was added: \"{item.get('new_value')}\". Read it before use.")

    return contexts


def build_health_context(scored_diff: dict[str, Any]) -> dict[str, Any]:
    """Aggregate audience-specific context for a whole scored diff."""
    all_contexts: list[dict[str, str]] = []
    for item in scored_diff.get("items", []):
        if item.get("significance", 0) < 10:
            continue  # skip rounding noise entirely
        all_contexts.extend(health_context_for_item(item))

    by_audience: dict[str, list[str]] = {}
    for ctx in all_contexts:
        by_audience.setdefault(ctx["audience"], []).append(ctx["statement"])

    return {
        "contexts": all_contexts,
        "by_audience": by_audience,
        "disclaimer": DISCLAIMER,
        "evidence_level": "deterministic_label_comparison",
    }
