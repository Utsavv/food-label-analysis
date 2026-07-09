from app.services.extraction.ingredient_normalizer import (
    normalize_ingredient_name,
    parse_ingredients,
    split_ingredient_list,
)


def test_split_respects_parentheses():
    parts = split_ingredient_list("Whey Protein (milk, soy), Cocoa Powder, Sucralose (INS 955)")
    assert parts == ["Whey Protein (milk, soy)", "Cocoa Powder", "Sucralose (INS 955)"]


def test_normalization_strips_parentheticals():
    assert normalize_ingredient_name("Whey Protein Concentrate (80%)") == "whey protein concentrate"
    assert normalize_ingredient_name("  Soy Lecithin (INS 322) ") == "soy lecithin"


def test_sweetener_detection_by_name_and_ins():
    entries = parse_ingredients("Sucralose (INS 955), Acesulfame K, Cocoa Powder")
    sucralose, ace_k, cocoa = entries
    assert sucralose.is_sweetener and sucralose.is_additive
    assert ace_k.is_sweetener
    assert not cocoa.is_sweetener and not cocoa.is_additive


def test_ins_number_alone_flags_sweetener():
    entries = parse_ingredients("Sweetener (INS 955)")
    assert entries[0].is_sweetener


def test_preservative_detection():
    entries = parse_ingredients("Potassium Sorbate (INS 202), Peanuts")
    assert entries[0].is_preservative
    assert entries[0].category == "preservative"
    assert not entries[1].is_preservative


def test_positions_follow_label_order():
    entries = parse_ingredients("Peanuts, Sugar, Salt")
    assert [(e.name_normalized, e.position) for e in entries] == [
        ("peanuts", 1), ("sugar", 2), ("salt", 3),
    ]
