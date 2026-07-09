"""Detect certifications, FSSAI license numbers and veg/non-veg marks in label text."""
import re

KNOWN_CERTIFICATIONS: dict[str, list[str]] = {
    "FSSAI": [r"\bfssai\b"],
    "ISO 22000": [r"\biso\s*22000\b"],
    "HACCP": [r"\bhaccp\b"],
    "GMP": [r"\bgmp\s*certified\b", r"\bgood manufacturing practices?\b"],
    "Informed Choice": [r"\binformed[\s-]?choice\b"],
    "Informed Sport": [r"\binformed[\s-]?sport\b"],
    "Labdoor": [r"\blabdoor\b"],
    "India Organic": [r"\bindia organic\b", r"\bjaivik bharat\b"],
    "USDA Organic": [r"\busda organic\b"],
    "Halal": [r"\bhalal\b"],
    "Kosher": [r"\bkosher\b"],
    "Non-GMO": [r"\bnon[\s-]?gmo\b"],
    "Vegan Certified": [r"\bvegan certified\b", r"\bcertified vegan\b"],
    "AGMARK": [r"\bagmark\b"],
}

# FSSAI license numbers are 14 digits.
FSSAI_LICENSE_PATTERN = re.compile(
    r"fssai\s*(?:lic(?:ense|\.)?\s*(?:no\.?|number)?|no\.?)?\s*[:#-]?\s*(\d{14})",
    re.IGNORECASE,
)

_VEG_PATTERNS = [r"\bvegetarian symbol\b", r"\bgreen dot\b", r"\b100% vegetarian\b", r"\bveg symbol\b",
                 r"\bsuitable for vegetarians\b", r"\bvegetarian\b"]
_NON_VEG_PATTERNS = [r"\bnon[\s-]?vegetarian\b", r"\bbrown dot\b", r"\bnon[\s-]?veg\b"]


def detect_certifications(text: str) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for name, patterns in KNOWN_CERTIFICATIONS.items():
        if any(re.search(p, lowered) for p in patterns):
            found.append(name)
    return found


def detect_fssai_license(text: str) -> str | None:
    m = FSSAI_LICENSE_PATTERN.search(text)
    return m.group(1) if m else None


def detect_veg_status(text: str) -> str | None:
    lowered = text.lower()
    # Check non-veg first: "non-vegetarian" contains "vegetarian".
    if any(re.search(p, lowered) for p in _NON_VEG_PATTERNS):
        return "non_vegetarian"
    if any(re.search(p, lowered) for p in _VEG_PATTERNS):
        return "vegetarian"
    return None
