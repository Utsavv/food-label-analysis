"""Deterministic parser: raw label text -> StructuredLabel.

Handles the semi-structured text produced by web extraction / OCR of Indian
food labels. Confidence is high for regex-anchored fields; anything the
parser cannot find is left as None ("not found on label/source") — never
invented. The LabelExtractionAgent can be used to assist on messy text, but
its output must conform to the same StructuredLabel schema.
"""
import re

from app.schemas import (
    AllergenEntry,
    ClaimEntry,
    FieldEvidence,
    NutrientValue,
    StructuredLabel,
)
from app.services.extraction.certification_detector import (
    detect_certifications,
    detect_fssai_license,
    detect_veg_status,
)
from app.services.extraction.ingredient_normalizer import parse_ingredients
from app.services.extraction.nutrition_normalizer import (
    normalize_amount,
    normalize_nutrient_name,
    parse_amount_string,
)

KNOWN_CLAIMS: dict[str, str] = {
    "high protein": "high_protein",
    "rich in protein": "high_protein",
    "no added sugar": "no_added_sugar",
    "zero added sugar": "no_added_sugar",
    "sugar free": "sugar_free",
    "gluten free": "gluten_free",
    "gluten-free": "gluten_free",
    "vegan": "vegan",
    "plant based": "plant_based",
    "plant-based": "plant_based",
    "organic": "organic",
    "fortified": "fortified",
    "no preservatives": "no_preservatives",
    "no artificial sweetener": "no_artificial_sweetener",
    "contains artificial sweetener": "contains_artificial_sweetener",
    "no artificial flavours": "no_artificial_flavours",
    "no artificial flavors": "no_artificial_flavours",
    "keto friendly": "keto_friendly",
    "low fat": "low_fat",
    "low carb": "low_carb",
    "immunity": "immunity_support",
    "lactose free": "lactose_free",
    "soy free": "soy_free",
}

COMMON_ALLERGENS = [
    "milk", "soy", "soya", "wheat", "gluten", "peanut", "peanuts", "tree nuts",
    "almond", "almonds", "cashew", "cashews", "walnut", "egg", "eggs", "fish",
    "shellfish", "crustacean", "sesame", "mustard", "sulphite", "sulfite", "lactose",
]

_NUTRITION_LINE = re.compile(
    r"^\s*(?P<name>[A-Za-z][A-Za-z0-9 ()/.-]{1,40}?)\s*[:\-]?\s+"
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>kcal|kj|mg|mcg|µg|g|kg|iu)\b"
    r"(?:\s*\(?\s*(?P<dv>\d+(?:\.\d+)?)\s*%\s*(?:rda|dv)?\s*\)?)?",
    re.IGNORECASE,
)

_SERVING_SIZE = re.compile(r"serving size\s*[:\-]?\s*([^\n,;]+)", re.IGNORECASE)
_SERVINGS_PER = re.compile(r"servings? per (?:container|pack|jar|box)\s*[:\-]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_INGREDIENTS = re.compile(r"^ingredients?\s*[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_CONTAINS = re.compile(r"\bcontains\s+([a-z ,&]+?)(?:\.|$|\n)", re.IGNORECASE)
_MAY_CONTAIN = re.compile(r"\bmay contain(?:\s+traces?\s+of)?\s+([a-z ,&]+?)(?:\.|$|\n)", re.IGNORECASE)
_WARNING = re.compile(r"^\s*(?:warning|caution|advisory)\s*[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_MANUFACTURER = re.compile(
    r"(?:manufactured|marketed|packed)\s+(?:and marketed\s+)?by\s*[:\-]?\s*([^\n]+)", re.IGNORECASE
)
_ORIGIN = re.compile(r"(?:country of origin|product of|made in)\s*[:\-]?\s*([A-Za-z ]+)", re.IGNORECASE)

# Section headers where a nutrition basis may be declared
_BASIS_100G = re.compile(r"per\s*100\s*(?:g|gm|grams?|ml)", re.IGNORECASE)

# Lines that look like nutrition but are not nutrients
_NOT_NUTRIENTS = {"serving_size", "servings_per_container", "net_weight", "net_quantity", "batch_no", "mrp"}


def _find_nutrition_basis(text: str) -> str:
    return "per_100g" if _BASIS_100G.search(text) else "per_serving"


def parse_nutrition_lines(text: str, basis: str) -> list[NutrientValue]:
    nutrients: list[NutrientValue] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = _NUTRITION_LINE.match(line)
        if not m:
            continue
        name = normalize_nutrient_name(m.group("name"))
        if not name or name in _NOT_NUTRIENTS or name in seen:
            continue
        amount = float(m.group("amount"))
        unit = m.group("unit").lower()
        amount, unit = normalize_amount(name, amount, unit)
        dv = float(m.group("dv")) if m.group("dv") else None
        nutrients.append(
            NutrientValue(
                name=name, amount=amount, unit=unit, basis=basis,
                daily_value_percent=dv, confidence=0.9, evidence=line.strip(),
            )
        )
        seen.add(name)
    return nutrients


def parse_allergens(text: str) -> list[AllergenEntry]:
    allergens: list[AllergenEntry] = []
    seen: set[tuple[str, str]] = set()

    def _collect(match_iter, presence: str) -> None:
        for m in match_iter:
            phrase = m.group(1).lower()
            for allergen in COMMON_ALLERGENS:
                if re.search(rf"\b{re.escape(allergen)}\b", phrase):
                    canonical = {"soya": "soy", "peanuts": "peanut", "almonds": "almond",
                                 "cashews": "cashew", "eggs": "egg", "sulfite": "sulphite"}.get(allergen, allergen)
                    key = (canonical, presence)
                    if key not in seen:
                        seen.add(key)
                        allergens.append(
                            AllergenEntry(name=canonical, presence_type=presence, evidence=m.group(0).strip())
                        )

    _collect(_MAY_CONTAIN.finditer(text), "may_contain")
    may_contain_spans = [m.span() for m in _MAY_CONTAIN.finditer(text)]

    def outside_may_contain(m) -> bool:
        return not any(s <= m.start() < e for s, e in may_contain_spans)

    _collect((m for m in _CONTAINS.finditer(text) if outside_may_contain(m)), "contains")
    return allergens


def parse_claims(text: str) -> list[ClaimEntry]:
    lowered = text.lower()
    claims: list[ClaimEntry] = []
    seen: set[str] = set()
    for phrase, normalized in KNOWN_CLAIMS.items():
        idx = lowered.find(phrase)
        if idx == -1 or normalized in seen:
            continue
        # "vegan" inside "vegan certified" is a certification, still fine as a claim too
        seen.add(normalized)
        claim_type = "nutrition" if normalized in (
            "high_protein", "no_added_sugar", "sugar_free", "low_fat", "low_carb",
        ) else "dietary"
        claims.append(
            ClaimEntry(
                claim_text=text[idx: idx + len(phrase)],
                normalized_claim=normalized,
                claim_type=claim_type,
                evidence=text[max(0, idx - 20): idx + len(phrase) + 20].strip(),
            )
        )
    return claims


def parse_label_text(raw_text: str) -> StructuredLabel:
    """Parse raw label/page text into the canonical structured label."""
    text = raw_text.replace("\r\n", "\n")

    label = StructuredLabel()

    if m := _SERVING_SIZE.search(text):
        label.serving_size = FieldEvidence(value=m.group(1).strip(), confidence=0.9, evidence=m.group(0).strip())
    if m := _SERVINGS_PER.search(text):
        label.servings_per_container = FieldEvidence(
            value=float(m.group(1)), confidence=0.9, evidence=m.group(0).strip()
        )

    basis = _find_nutrition_basis(text)
    label.nutrition = parse_nutrition_lines(text, basis)

    if m := _INGREDIENTS.search(text):
        label.ingredients = parse_ingredients(m.group(1))

    label.allergens = parse_allergens(text)
    label.certifications = detect_certifications(text)
    label.claims = parse_claims(text)
    label.warnings = [m.group(1).strip() for m in _WARNING.finditer(text)]

    if m := _MANUFACTURER.search(text):
        label.manufacturer_info = FieldEvidence(value=m.group(1).strip(), confidence=0.8, evidence=m.group(0).strip())
    if fssai := detect_fssai_license(text):
        label.fssai_license = FieldEvidence(value=fssai, confidence=0.95, evidence=f"FSSAI {fssai}")
    if veg := detect_veg_status(text):
        label.veg_status = FieldEvidence(value=veg, confidence=0.85, evidence=veg.replace("_", "-"))
    if m := _ORIGIN.search(text):
        label.country_of_origin = FieldEvidence(value=m.group(1).strip(), confidence=0.8, evidence=m.group(0).strip())

    # Overall confidence: average of populated anchor fields
    scores = [f.confidence for f in (label.serving_size, label.fssai_license, label.veg_status) if f.value]
    scores += [n.confidence for n in label.nutrition]
    scores += [0.9] if label.ingredients else []
    label.overall_confidence = round(sum(scores) / len(scores), 3) if scores else 0.1
    return label


def parse_serving_size_grams(serving_size_value: str | None) -> float | None:
    """Extract grams from a serving size string like '30 g (1 scoop)'."""
    if not serving_size_value:
        return None
    amount, unit = parse_amount_string(str(serving_size_value))
    if amount is None:
        return None
    if unit == "kg":
        return amount * 1000
    if unit in ("g", None):
        return amount
    return None
