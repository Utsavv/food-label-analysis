from app.services.comparison.significance_scoring import level_for, score_diff, score_diff_item


def test_allergen_added_is_very_high():
    item = {"type": "allergen_added", "field": "peanut", "presence_type": "contains"}
    assert score_diff_item(item) >= 90


def test_certification_removed_is_high():
    assert score_diff_item({"type": "certification_removed", "field": "Informed Choice"}) >= 60


def test_minor_rounding_is_low():
    item = {"type": "nutrient_amount_changed", "field": "protein",
            "old_value": 24.0, "new_value": 23.9, "percent_change": -0.4}
    assert score_diff_item(item) < 10


def test_material_protein_drop_in_protein_powder_is_high():
    item = {"type": "nutrient_amount_changed", "field": "protein",
            "old_value": 24.0, "new_value": 22.0, "percent_change": -8.3}
    assert score_diff_item(item, category="protein_powder") >= 80


def test_protein_increase_is_less_concerning_than_decrease():
    up = {"type": "nutrient_amount_changed", "field": "protein",
          "old_value": 22.0, "new_value": 24.0, "percent_change": 9.1}
    down = {"type": "nutrient_amount_changed", "field": "protein",
            "old_value": 24.0, "new_value": 22.0, "percent_change": -8.3}
    assert score_diff_item(up, "protein_powder") < score_diff_item(down, "protein_powder")


def test_added_sugar_from_zero_is_material():
    item = {"type": "nutrient_amount_changed", "field": "added_sugar",
            "old_value": 0.0, "new_value": 4.0, "percent_change": None}
    assert score_diff_item(item, category="protein_bar") >= 80


def test_sweetener_added_is_medium():
    item = {"type": "ingredient_added", "field": "sucralose", "is_sweetener": True}
    assert 35 <= score_diff_item(item) < 60


def test_key_ingredient_reorder_beats_minor_reorder():
    key = {"type": "ingredient_reordered", "field": "sugar", "old_value": 5, "new_value": 2,
           "is_key_ingredient": True}
    minor = {"type": "ingredient_reordered", "field": "salt", "old_value": 7, "new_value": 9,
             "is_key_ingredient": False}
    assert score_diff_item(key) > score_diff_item(minor)


def test_overall_score_and_levels():
    diff = {"items": [
        {"type": "allergen_added", "field": "soy", "presence_type": "contains"},
        {"type": "claim_removed", "field": "no_added_sugar"},
    ]}
    scored = score_diff(diff, category="protein_bar")
    assert scored["overall_score"] >= 95
    assert scored["overall_level"] == "very_high"
    assert all("significance" in i and "significance_level" in i for i in scored["items"])


def test_empty_diff_scores_zero():
    assert score_diff({"items": []})["overall_score"] == 0.0


def test_levels():
    assert level_for(95) == "very_high"
    assert level_for(65) == "high"
    assert level_for(40) == "medium"
    assert level_for(15) == "low"
    assert level_for(3) == "minimal"
