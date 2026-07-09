"""Normalize ingredient names and flag additives, sweeteners and preservatives."""
import re

from app.schemas import IngredientEntry

# Known artificial/intense sweeteners (names + Indian INS numbers)
SWEETENERS = {
    "sucralose": "INS 955",
    "aspartame": "INS 951",
    "acesulfame potassium": "INS 950",
    "acesulfame k": "INS 950",
    "saccharin": "INS 954",
    "sodium saccharin": "INS 954",
    "steviol glycosides": "INS 960",
    "stevia": "INS 960",
    "neotame": "INS 961",
    "maltitol": "INS 965",
    "sorbitol": "INS 420",
    "xylitol": "INS 967",
    "erythritol": "INS 968",
}

PRESERVATIVES = {
    "potassium sorbate": "INS 202",
    "sodium benzoate": "INS 211",
    "sorbic acid": "INS 200",
    "benzoic acid": "INS 210",
    "calcium propionate": "INS 282",
    "bha": "INS 320",
    "bht": "INS 321",
    "tbhq": "INS 319",
}

# Common non-sweetener, non-preservative additives seen in protein products
OTHER_ADDITIVES = {
    "soy lecithin": "INS 322",
    "sunflower lecithin": "INS 322",
    "lecithin": "INS 322",
    "xanthan gum": "INS 415",
    "guar gum": "INS 412",
    "carrageenan": "INS 407",
    "silicon dioxide": "INS 551",
    "cellulose gum": "INS 466",
    "glycerin": "INS 422",
    "glycerol": "INS 422",
    "citric acid": "INS 330",
    "malic acid": "INS 296",
    "artificial flavour": None,
    "artificial flavor": None,
    "nature identical flavour": None,
}

_INS_PATTERN = re.compile(r"\bins\s*[-.]?\s*(\d{3,4}[a-z]?)\b", re.IGNORECASE)
_E_NUMBER_PATTERN = re.compile(r"\be\s*[-.]?\s*(\d{3,4}[a-z]?)\b", re.IGNORECASE)

_SWEETENER_INS = {v.split()[-1].lower() for v in SWEETENERS.values() if v}
_PRESERVATIVE_INS = {v.split()[-1].lower() for v in PRESERVATIVES.values() if v}


def normalize_ingredient_name(raw: str) -> str:
    name = raw.strip().lower()
    # Drop parenthetical qualifiers ("(80%)", "(INS 322)") so that a tweaked
    # percentage does not read as a removed + added ingredient in the diff.
    name = re.sub(r"\([^)]*\)", " ", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip(" .;,-")
    return name


def _match_known(name: str, table: dict[str, str | None]) -> bool:
    return any(key in name for key in table)


def _ins_numbers(name: str) -> set[str]:
    nums = {m.group(1).lower() for m in _INS_PATTERN.finditer(name)}
    nums |= {m.group(1).lower() for m in _E_NUMBER_PATTERN.finditer(name)}
    return nums


def classify_ingredient(raw: str, position: int) -> IngredientEntry:
    normalized = normalize_ingredient_name(raw)
    # Classify against the raw text too: INS numbers usually sit in the
    # parentheses that normalization strips.
    raw_lower = re.sub(r"\s+", " ", raw.strip().lower())
    ins = _ins_numbers(raw_lower)

    is_sweetener = _match_known(raw_lower, SWEETENERS) or bool(ins & _SWEETENER_INS)
    is_preservative = (
        _match_known(raw_lower, PRESERVATIVES)
        or "preservative" in raw_lower
        or bool(ins & _PRESERVATIVE_INS)
    )
    is_additive = (
        is_sweetener
        or is_preservative
        or _match_known(raw_lower, OTHER_ADDITIVES)
        or bool(ins)
        or any(w in raw_lower for w in ("emulsifier", "stabilizer", "stabiliser",
                                        "thickener", "anti-caking", "acidity regulator",
                                        "flavour", "flavor", "colour", "color"))
    )

    category = None
    if is_sweetener:
        category = "sweetener"
    elif is_preservative:
        category = "preservative"
    elif is_additive:
        category = "additive"

    return IngredientEntry(
        name_raw=raw.strip(),
        name_normalized=normalized,
        position=position,
        is_additive=is_additive,
        is_sweetener=is_sweetener,
        is_preservative=is_preservative,
        category=category,
    )


def split_ingredient_list(text: str) -> list[str]:
    """Split an ingredient declaration on commas, respecting parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return [p.strip(" .") for p in parts if p.strip(" .")]


def parse_ingredients(text: str) -> list[IngredientEntry]:
    return [classify_ingredient(raw, i + 1) for i, raw in enumerate(split_ingredient_list(text))]
