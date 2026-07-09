"""Normalize nutrient names, units and amounts to canonical form.

Canonical keys: energy_kcal, protein, carbohydrates, total_sugar, added_sugar,
fat, saturated_fat, trans_fat, sodium, fiber, plus pass-through for vitamins
and minerals. Sodium is normalized to mg; most others to g; energy to kcal.
"""
import re

NUTRIENT_SYNONYMS: dict[str, str] = {
    "energy": "energy_kcal",
    "calories": "energy_kcal",
    "calorie": "energy_kcal",
    "energy (kcal)": "energy_kcal",
    "protein": "protein",
    "proteins": "protein",
    "carbohydrate": "carbohydrates",
    "carbohydrates": "carbohydrates",
    "total carbohydrate": "carbohydrates",
    "total carbohydrates": "carbohydrates",
    "sugar": "total_sugar",
    "sugars": "total_sugar",
    "total sugar": "total_sugar",
    "total sugars": "total_sugar",
    "added sugar": "added_sugar",
    "added sugars": "added_sugar",
    "fat": "fat",
    "total fat": "fat",
    "saturated fat": "saturated_fat",
    "saturated fatty acids": "saturated_fat",
    "trans fat": "trans_fat",
    "trans fatty acids": "trans_fat",
    "sodium": "sodium",
    "fiber": "fiber",
    "fibre": "fiber",
    "dietary fiber": "fiber",
    "dietary fibre": "fiber",
    "cholesterol": "cholesterol",
    "calcium": "calcium",
    "iron": "iron",
    "potassium": "potassium",
    "vitamin d": "vitamin_d",
    "vitamin c": "vitamin_c",
    "vitamin b12": "vitamin_b12",
}

# Target unit per canonical nutrient. Anything not listed keeps its unit.
TARGET_UNITS: dict[str, str] = {
    "energy_kcal": "kcal",
    "protein": "g",
    "carbohydrates": "g",
    "total_sugar": "g",
    "added_sugar": "g",
    "fat": "g",
    "saturated_fat": "g",
    "trans_fat": "g",
    "sodium": "mg",
    "fiber": "g",
    "cholesterol": "mg",
    "calcium": "mg",
    "iron": "mg",
    "potassium": "mg",
}

_UNIT_FACTORS_TO_G = {"g": 1.0, "mg": 0.001, "mcg": 0.000001, "µg": 0.000001, "kg": 1000.0}


def normalize_nutrient_name(raw_name: str) -> str:
    key = re.sub(r"\s+", " ", raw_name.strip().lower())
    key = key.rstrip(":").strip()
    if key in NUTRIENT_SYNONYMS:
        return NUTRIENT_SYNONYMS[key]
    return re.sub(r"[^a-z0-9]+", "_", key).strip("_")


def normalize_amount(name: str, amount: float | None, unit: str | None) -> tuple[float | None, str | None]:
    """Convert an amount to the canonical unit for the nutrient, if known."""
    if amount is None:
        return None, unit
    unit_l = (unit or "").strip().lower()
    target = TARGET_UNITS.get(name)
    if target is None or unit_l == target:
        return round(amount, 4), unit_l or unit
    if target == "kcal":
        if unit_l in ("kj", "kilojoule", "kilojoules"):
            return round(amount / 4.184, 1), "kcal"
        return round(amount, 4), unit_l or "kcal"
    if unit_l in _UNIT_FACTORS_TO_G and target in ("g", "mg"):
        grams = amount * _UNIT_FACTORS_TO_G[unit_l]
        value = grams if target == "g" else grams * 1000.0
        return round(value, 4), target
    return round(amount, 4), unit_l or unit


def parse_amount_string(text: str) -> tuple[float | None, str | None]:
    """Parse '24 g', '120kcal', '0.5g' style strings into (amount, unit)."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kcal|kj|mg|mcg|µg|g|kg|iu|%)?", text.strip(), re.IGNORECASE)
    if not m:
        return None, None
    amount = float(m.group(1))
    unit = m.group(2).lower() if m.group(2) else None
    return amount, unit
