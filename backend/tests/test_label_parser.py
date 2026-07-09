from pathlib import Path

from app.services.extraction.label_parser import parse_label_text

FIXTURES = Path(__file__).resolve().parents[1] / "seed" / "fixtures"


def test_parses_full_indian_label():
    label = parse_label_text((FIXTURES / "maxfit_whey_v1.txt").read_text())

    assert label.serving_size.value == "30 g (1 heaped scoop)"
    assert label.servings_per_container.value == 33

    nutrition = {n.name: n for n in label.nutrition}
    assert nutrition["protein"].amount == 24.0
    assert nutrition["sodium"].amount == 120.0 and nutrition["sodium"].unit == "mg"
    assert nutrition["protein"].evidence  # evidence text captured

    assert label.ingredients[0].name_normalized == "whey protein concentrate"
    assert {a.name for a in label.allergens} == {"milk", "soy"}
    assert "FSSAI" in label.certifications and "ISO 22000" in label.certifications
    assert {c.normalized_claim for c in label.claims} >= {"high_protein", "no_added_sugar", "gluten_free"}
    assert label.fssai_license.value == "10012345000123"
    assert label.veg_status.value == "vegetarian"
    assert label.warnings
    assert label.overall_confidence > 0.5


def test_missing_fields_are_not_invented():
    label = parse_label_text("Just a marketing page with no label data at all.")
    assert label.serving_size.value is None
    assert label.fssai_license.value is None
    assert label.nutrition == []
    assert label.overall_confidence < 0.5


def test_may_contain_vs_contains():
    text = "Allergen Information: Contains milk. May contain traces of tree nuts and cashew."
    label = parse_label_text(text)
    presence = {a.name: a.presence_type for a in label.allergens}
    assert presence["milk"] == "contains"
    assert presence["cashew"] == "may_contain"
    assert presence["tree nuts"] == "may_contain"
