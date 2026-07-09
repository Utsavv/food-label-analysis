from app.services.extraction.nutrition_normalizer import (
    normalize_amount,
    normalize_nutrient_name,
    parse_amount_string,
)


def test_synonyms_map_to_canonical_names():
    assert normalize_nutrient_name("Energy") == "energy_kcal"
    assert normalize_nutrient_name("Calories") == "energy_kcal"
    assert normalize_nutrient_name("Total Sugars") == "total_sugar"
    assert normalize_nutrient_name("Added Sugar") == "added_sugar"
    assert normalize_nutrient_name("Dietary Fibre") == "fiber"
    assert normalize_nutrient_name("Trans Fatty Acids") == "trans_fat"


def test_unknown_names_become_snake_case():
    assert normalize_nutrient_name("Vitamin B6") == "vitamin_b6"
    assert normalize_nutrient_name("Omega-3 Fatty Acids") == "omega_3_fatty_acids"


def test_sodium_normalizes_to_mg():
    assert normalize_amount("sodium", 0.19, "g") == (190.0, "mg")
    assert normalize_amount("sodium", 190, "mg") == (190.0, "mg")


def test_protein_normalizes_to_g():
    assert normalize_amount("protein", 24000, "mg") == (24.0, "g")
    assert normalize_amount("protein", 24, "g") == (24.0, "g")


def test_energy_kj_converts_to_kcal():
    amount, unit = normalize_amount("energy_kcal", 500, "kJ")
    assert unit == "kcal"
    assert abs(amount - 119.5) < 0.1


def test_parse_amount_string():
    assert parse_amount_string("24 g") == (24.0, "g")
    assert parse_amount_string("120kcal") == (120.0, "kcal")
    assert parse_amount_string("no numbers here") == (None, None)
