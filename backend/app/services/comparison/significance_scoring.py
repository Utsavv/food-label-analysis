"""Rule-based significance scoring (0-100) for label diffs.

Thresholds are configurable per nutrient and per product category, so new
food categories can tune sensitivity without code changes.
"""
from typing import Any

# Base score per diff type (before nutrient/category adjustments)
BASE_SCORES: dict[str, float] = {
    "allergen_added": 95.0,
    "allergen_removed": 65.0,       # may reflect formulation OR disclosure change
    "certification_removed": 80.0,
    "certification_added": 40.0,
    "claim_removed": 55.0,
    "claim_added": 35.0,
    "serving_size_changed": 60.0,   # can hide nutrition changes
    "warning_added": 70.0,
    "warning_removed": 50.0,
    "fssai_license_changed": 45.0,
    "veg_status_changed": 90.0,
    "ingredient_removed": 40.0,
    "nutrient_added": 30.0,
    "nutrient_removed": 45.0,
    "label_text_changed_unknown_significance": 25.0,
}

# Percent-change thresholds per nutrient: (minor_pct, material_pct, direction_of_concern)
# direction "up" = increase is the concern, "down" = decrease is the concern.
NUTRIENT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "added_sugar": {"minor": 5, "material": 15, "concern": "up", "material_score": 85, "minor_score": 20},
    "total_sugar": {"minor": 5, "material": 20, "concern": "up", "material_score": 70, "minor_score": 15},
    "sodium": {"minor": 5, "material": 15, "concern": "up", "material_score": 72, "minor_score": 15},
    "protein": {"minor": 3, "material": 8, "concern": "down", "material_score": 80, "minor_score": 15},
    "saturated_fat": {"minor": 5, "material": 20, "concern": "up", "material_score": 65, "minor_score": 15},
    "trans_fat": {"minor": 0, "material": 1, "concern": "up", "material_score": 85, "minor_score": 40},
    "energy_kcal": {"minor": 5, "material": 15, "concern": "up", "material_score": 50, "minor_score": 10},
    "fiber": {"minor": 10, "material": 30, "concern": "down", "material_score": 40, "minor_score": 10},
    "_default": {"minor": 5, "material": 25, "concern": "any", "material_score": 45, "minor_score": 10},
}

# Category-specific overrides, e.g. protein loss matters most in protein products.
CATEGORY_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "protein_powder": {
        "protein": {"minor": 2, "material": 5, "concern": "down", "material_score": 85, "minor_score": 20},
    },
    "protein_bar": {
        "protein": {"minor": 3, "material": 8, "concern": "down", "material_score": 80, "minor_score": 20},
        "added_sugar": {"minor": 5, "material": 12, "concern": "up", "material_score": 85, "minor_score": 20},
    },
}


def _nutrient_config(nutrient: str, category: str | None) -> dict[str, Any]:
    if category and nutrient in CATEGORY_OVERRIDES.get(category, {}):
        return CATEGORY_OVERRIDES[category][nutrient]
    return NUTRIENT_THRESHOLDS.get(nutrient, NUTRIENT_THRESHOLDS["_default"])


def score_diff_item(item: dict[str, Any], category: str | None = None) -> float:
    """Score a single diff item 0-100."""
    dtype = item["type"]

    if dtype == "nutrient_amount_changed":
        cfg = _nutrient_config(item.get("field", ""), category)
        pct = item.get("percent_change")
        old_v, new_v = item.get("old_value"), item.get("new_value")
        if pct is None:
            # old == 0 -> percent undefined. Appearing from zero (e.g. added
            # sugar 0 -> 4 g) is material when increases are the concern.
            if old_v == 0 and new_v and new_v > 0 and cfg["concern"] in ("up", "any"):
                return float(cfg["material_score"])
            # Unit change or other unquantifiable difference: medium.
            return 40.0
        direction = "up" if pct > 0 else "down"
        magnitude = abs(pct)
        concern = cfg["concern"]
        concerning = concern == "any" or direction == concern
        if magnitude < cfg["minor"]:
            return 5.0  # rounding noise
        if magnitude >= cfg["material"]:
            base = cfg["material_score"] if concerning else cfg["material_score"] * 0.5
            # scale slightly with magnitude beyond the material threshold
            bonus = min(15.0, (magnitude - cfg["material"]) * 0.3)
            return min(100.0, base + bonus)
        return cfg["minor_score"] if concerning else cfg["minor_score"] * 0.5

    if dtype == "ingredient_added":
        if item.get("is_sweetener"):
            return 55.0  # artificial sweetener added: medium
        if item.get("is_preservative"):
            return 50.0
        if item.get("is_additive"):
            return 45.0
        return 30.0

    if dtype == "ingredient_reordered":
        return 45.0 if item.get("is_key_ingredient") else 15.0

    if dtype == "allergen_removed" and item.get("presence_type") == "may_contain":
        return 50.0  # trace-disclosure removal slightly lower than "contains" removal

    return BASE_SCORES.get(dtype, 25.0)


def score_diff(diff_json: dict[str, Any], category: str | None = None) -> dict[str, Any]:
    """Score every item and compute an overall 0-100 significance.

    Overall = max item score, nudged up when several independent
    medium/high changes co-occur, capped at 100.
    """
    items = diff_json.get("items", [])
    scored_items = []
    for item in items:
        s = round(score_diff_item(item, category), 1)
        scored_items.append({**item, "significance": s, "significance_level": level_for(s)})

    if not scored_items:
        return {"items": [], "overall_score": 0.0, "overall_level": "none"}

    scores = sorted((i["significance"] for i in scored_items), reverse=True)
    overall = scores[0]
    for extra in scores[1:4]:
        if extra >= 40:
            overall += extra * 0.05  # co-occurring meaningful changes raise urgency a bit
    overall = round(min(100.0, overall), 1)

    return {"items": scored_items, "overall_score": overall, "overall_level": level_for(overall)}


def level_for(score: float) -> str:
    if score >= 80:
        return "very_high"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    if score >= 10:
        return "low"
    return "minimal"
