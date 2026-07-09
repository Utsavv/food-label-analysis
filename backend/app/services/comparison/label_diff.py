"""Deterministic diff between two StructuredLabel JSON payloads.

Produces a list of typed diff items. LLM agents never diff — they only
explain the diff produced here.
"""
import hashlib
import json
from typing import Any

DIFF_TYPES = [
    "nutrient_added", "nutrient_removed", "nutrient_amount_changed",
    "ingredient_added", "ingredient_removed", "ingredient_reordered",
    "allergen_added", "allergen_removed",
    "certification_added", "certification_removed",
    "claim_added", "claim_removed",
    "serving_size_changed",
    "warning_added", "warning_removed",
    "fssai_license_changed", "veg_status_changed",
    "label_text_changed_unknown_significance",
]


def compute_version_hash(structured_json: dict) -> str:
    """Stable hash of label content, ignoring confidence/evidence noise."""
    content = _content_signature(structured_json)
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def _content_signature(s: dict) -> dict:
    return {
        "serving_size": (s.get("serving_size") or {}).get("value"),
        "servings_per_container": (s.get("servings_per_container") or {}).get("value"),
        "nutrition": sorted(
            [n["name"], n.get("amount"), n.get("unit"), n.get("basis")]
            for n in s.get("nutrition", [])
        ),
        "ingredients": [i["name_normalized"] for i in s.get("ingredients", [])],
        "allergens": sorted([a["name"], a.get("presence_type")] for a in s.get("allergens", [])),
        "certifications": sorted(s.get("certifications", [])),
        "claims": sorted(c["normalized_claim"] for c in s.get("claims", [])),
        "warnings": sorted(s.get("warnings", [])),
        "fssai_license": (s.get("fssai_license") or {}).get("value"),
        "veg_status": (s.get("veg_status") or {}).get("value"),
    }


def _nutrition_map(s: dict) -> dict[str, dict]:
    return {n["name"]: n for n in s.get("nutrition", [])}


def _pct_change(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return round((new - old) / old * 100.0, 1)


def diff_labels(old: dict, new: dict) -> dict[str, Any]:
    """Compare two structured label dicts. Returns {"items": [...], "summary_counts": {...}}."""
    items: list[dict] = []

    # --- Serving size ---
    old_ss = (old.get("serving_size") or {}).get("value")
    new_ss = (new.get("serving_size") or {}).get("value")
    if old_ss != new_ss and (old_ss or new_ss):
        items.append({
            "type": "serving_size_changed",
            "field": "serving_size",
            "old_value": old_ss, "new_value": new_ss,
            "detail": f"Serving size changed from '{old_ss}' to '{new_ss}'",
        })

    # --- Nutrition ---
    old_nut, new_nut = _nutrition_map(old), _nutrition_map(new)
    for name in sorted(new_nut.keys() - old_nut.keys()):
        n = new_nut[name]
        items.append({
            "type": "nutrient_added", "field": name,
            "old_value": None, "new_value": n.get("amount"), "unit": n.get("unit"),
            "detail": f"{name} now listed: {n.get('amount')} {n.get('unit') or ''}".strip(),
        })
    for name in sorted(old_nut.keys() - new_nut.keys()):
        n = old_nut[name]
        items.append({
            "type": "nutrient_removed", "field": name,
            "old_value": n.get("amount"), "new_value": None, "unit": n.get("unit"),
            "detail": f"{name} no longer listed (was {n.get('amount')} {n.get('unit') or ''})".strip(),
        })
    for name in sorted(old_nut.keys() & new_nut.keys()):
        o, n = old_nut[name], new_nut[name]
        if o.get("amount") == n.get("amount") and o.get("unit") == n.get("unit"):
            continue
        pct = None
        if o.get("amount") is not None and n.get("amount") is not None and o.get("unit") == n.get("unit"):
            pct = _pct_change(o["amount"], n["amount"])
        items.append({
            "type": "nutrient_amount_changed", "field": name,
            "old_value": o.get("amount"), "new_value": n.get("amount"),
            "unit": n.get("unit") or o.get("unit"), "percent_change": pct,
            "detail": (
                f"{name} changed from {o.get('amount')} {o.get('unit') or ''} "
                f"to {n.get('amount')} {n.get('unit') or ''}"
            ).strip(),
        })

    # --- Ingredients ---
    old_ing = [i["name_normalized"] for i in old.get("ingredients", [])]
    new_ing = [i["name_normalized"] for i in new.get("ingredients", [])]
    new_ing_meta = {i["name_normalized"]: i for i in new.get("ingredients", [])}
    old_ing_meta = {i["name_normalized"]: i for i in old.get("ingredients", [])}

    for name in [i for i in new_ing if i not in old_ing]:
        meta = new_ing_meta[name]
        items.append({
            "type": "ingredient_added", "field": name,
            "old_value": None, "new_value": name,
            "position": meta.get("position"),
            "is_sweetener": meta.get("is_sweetener", False),
            "is_preservative": meta.get("is_preservative", False),
            "is_additive": meta.get("is_additive", False),
            "detail": f"New ingredient: {name} (position {meta.get('position')})",
        })
    for name in [i for i in old_ing if i not in new_ing]:
        items.append({
            "type": "ingredient_removed", "field": name,
            "old_value": name, "new_value": None,
            "detail": f"Ingredient removed: {name}",
        })
    # Reorder detection among common ingredients (order = proportion on Indian labels)
    common = [i for i in old_ing if i in new_ing]
    for name in common:
        old_pos, new_pos = old_ing.index(name) + 1, new_ing.index(name) + 1
        if abs(old_pos - new_pos) >= 2:
            items.append({
                "type": "ingredient_reordered", "field": name,
                "old_value": old_pos, "new_value": new_pos,
                "is_key_ingredient": old_pos <= 3 or new_pos <= 3,
                "detail": f"Ingredient '{name}' moved from position {old_pos} to {new_pos}",
            })

    # --- Allergens ---
    old_all = {(a["name"], a.get("presence_type", "contains")) for a in old.get("allergens", [])}
    new_all = {(a["name"], a.get("presence_type", "contains")) for a in new.get("allergens", [])}
    for name, presence in sorted(new_all - old_all):
        items.append({
            "type": "allergen_added", "field": name, "presence_type": presence,
            "old_value": None, "new_value": name,
            "detail": f"Allergen disclosure added: {name} ({presence.replace('_', ' ')})",
        })
    for name, presence in sorted(old_all - new_all):
        items.append({
            "type": "allergen_removed", "field": name, "presence_type": presence,
            "old_value": name, "new_value": None,
            "detail": f"Allergen disclosure removed: {name} ({presence.replace('_', ' ')})",
        })

    # --- Certifications ---
    old_cert, new_cert = set(old.get("certifications", [])), set(new.get("certifications", []))
    for name in sorted(new_cert - old_cert):
        items.append({"type": "certification_added", "field": name, "old_value": None,
                      "new_value": name, "detail": f"Certification added: {name}"})
    for name in sorted(old_cert - new_cert):
        items.append({"type": "certification_removed", "field": name, "old_value": name,
                      "new_value": None, "detail": f"Certification no longer shown: {name}"})

    # --- Claims ---
    old_claims = {c["normalized_claim"]: c for c in old.get("claims", [])}
    new_claims = {c["normalized_claim"]: c for c in new.get("claims", [])}
    for name in sorted(new_claims.keys() - old_claims.keys()):
        items.append({"type": "claim_added", "field": name, "old_value": None, "new_value": name,
                      "detail": f"Claim added: '{new_claims[name].get('claim_text', name)}'"})
    for name in sorted(old_claims.keys() - new_claims.keys()):
        items.append({"type": "claim_removed", "field": name, "old_value": name, "new_value": None,
                      "detail": f"Claim removed: '{old_claims[name].get('claim_text', name)}'"})

    # --- Warnings ---
    old_warn, new_warn = set(old.get("warnings", [])), set(new.get("warnings", []))
    for w in sorted(new_warn - old_warn):
        items.append({"type": "warning_added", "field": "warning", "old_value": None,
                      "new_value": w, "detail": f"Warning added: {w}"})
    for w in sorted(old_warn - new_warn):
        items.append({"type": "warning_removed", "field": "warning", "old_value": w,
                      "new_value": None, "detail": f"Warning removed: {w}"})

    # --- FSSAI / veg status ---
    old_fssai = (old.get("fssai_license") or {}).get("value")
    new_fssai = (new.get("fssai_license") or {}).get("value")
    if old_fssai != new_fssai and (old_fssai or new_fssai):
        items.append({"type": "fssai_license_changed", "field": "fssai_license",
                      "old_value": old_fssai, "new_value": new_fssai,
                      "detail": f"FSSAI license changed from {old_fssai} to {new_fssai}"})

    old_veg = (old.get("veg_status") or {}).get("value")
    new_veg = (new.get("veg_status") or {}).get("value")
    if old_veg != new_veg and (old_veg or new_veg):
        items.append({"type": "veg_status_changed", "field": "veg_status",
                      "old_value": old_veg, "new_value": new_veg,
                      "detail": f"Veg/non-veg mark changed from {old_veg} to {new_veg}"})

    # --- Fallback: hash differs but no structured diff found ---
    if not items and compute_version_hash(old) != compute_version_hash(new):
        items.append({
            "type": "label_text_changed_unknown_significance", "field": "label_text",
            "old_value": None, "new_value": None,
            "detail": "Label text changed but no structured field difference was detected",
        })

    counts: dict[str, int] = {}
    for item in items:
        counts[item["type"]] = counts.get(item["type"], 0) + 1

    return {"items": items, "summary_counts": counts, "total_changes": len(items)}
