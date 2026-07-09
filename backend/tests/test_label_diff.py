from pathlib import Path

from app.services.comparison.label_diff import compute_version_hash, diff_labels
from app.services.extraction.label_parser import parse_label_text

FIXTURES = Path(__file__).resolve().parents[1] / "seed" / "fixtures"


def _label(name: str) -> dict:
    return parse_label_text((FIXTURES / name).read_text()).model_dump()


def test_hash_is_stable_for_identical_content():
    a = _label("maxfit_whey_v1.txt")
    b = _label("maxfit_whey_v1.txt")
    assert compute_version_hash(a) == compute_version_hash(b)


def test_hash_changes_when_label_changes():
    assert compute_version_hash(_label("maxfit_whey_v1.txt")) != compute_version_hash(
        _label("maxfit_whey_v2.txt")
    )


def test_identical_labels_produce_empty_diff():
    a = _label("maxfit_whey_v1.txt")
    diff = diff_labels(a, a)
    assert diff["items"] == []
    assert diff["total_changes"] == 0


def test_powder_scenario_detects_expected_changes():
    diff = diff_labels(_label("maxfit_whey_v1.txt"), _label("maxfit_whey_v2.txt"))
    by_type = diff["summary_counts"]
    items = {(i["type"], i.get("field")) for i in diff["items"]}

    assert ("nutrient_amount_changed", "sodium") in items
    assert ("nutrient_amount_changed", "protein") in items
    assert ("ingredient_added", "sucralose") in items
    sucralose = next(i for i in diff["items"] if i.get("field") == "sucralose")
    assert sucralose["is_sweetener"] is True
    assert by_type["nutrient_amount_changed"] >= 3


def test_bar_scenario_detects_allergen_and_claim_changes():
    diff = diff_labels(_label("nutricrunch_bar_v1.txt"), _label("nutricrunch_bar_v2.txt"))
    items = {(i["type"], i.get("field")) for i in diff["items"]}

    assert ("allergen_added", "soy") in items
    assert ("allergen_added", "tree nuts") in items
    assert ("claim_removed", "no_added_sugar") in items
    assert ("nutrient_amount_changed", "added_sugar") in items


def test_percent_change_computed():
    diff = diff_labels(_label("maxfit_whey_v1.txt"), _label("maxfit_whey_v2.txt"))
    sodium = next(i for i in diff["items"] if i.get("field") == "sodium")
    assert sodium["percent_change"] == 58.3
