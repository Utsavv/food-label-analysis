"""Agent behaviour: prompt/schema validation with mocked LLM responses."""
import json
from pathlib import Path

from app.agents import adk_runtime
from app.agents.adk_runtime import load_prompt
from app.agents.change_analysis_agent import run_change_analysis
from app.agents.health_context_agent import run_health_context
from app.agents.ingredient_explainer_agent import run_ingredient_explainer
from app.agents.label_extraction_agent import run_extraction
from app.schemas import StructuredLabel

PROMPTS = Path(__file__).resolve().parents[1] / "app" / "prompts"


def test_all_prompts_are_versioned():
    for prompt_file in PROMPTS.glob("*.md"):
        _, version = load_prompt(prompt_file.name)
        assert version.startswith("v"), f"{prompt_file.name} missing PROMPT_VERSION"


def test_mock_mode_never_calls_llm(monkeypatch):
    called = []
    monkeypatch.setattr(adk_runtime, "adk_available", lambda: called.append(1) or False)
    result = run_ingredient_explainer("sucralose")
    assert result["model_name"] == "mock-rule-based"


def test_extraction_agent_valid_llm_response_used(monkeypatch):
    """When the mocked LLM returns schema-valid JSON, it is accepted."""
    valid = StructuredLabel().model_dump()
    valid["serving_size"] = {"value": "30 g", "confidence": 0.9, "evidence": "Serving Size: 30 g"}
    monkeypatch.setattr(
        "app.agents.label_extraction_agent.run_agent_json", lambda *a, **k: valid
    )
    # Low-confidence text forces the agent path
    label, model, version = run_extraction("blurry ocr text no structure")
    assert label.serving_size.value == "30 g"
    assert version == "v1.0"


def test_extraction_agent_invalid_llm_response_rejected(monkeypatch):
    """Schema-invalid LLM output must be discarded for the deterministic parse."""
    monkeypatch.setattr(
        "app.agents.label_extraction_agent.run_agent_json",
        lambda *a, **k: {"nutrition": "protein is 900g trust me"},
    )
    label, model, _ = run_extraction("blurry ocr text no structure")
    assert model == "deterministic-parser"
    assert label.nutrition == []  # nothing invented


def test_change_analysis_llm_cannot_override_score(monkeypatch):
    """Facts (scores) always come from deterministic code, not the LLM."""
    monkeypatch.setattr(
        "app.agents.change_analysis_agent.run_agent_json",
        lambda *a, **k: {
            "summary": "s", "what_changed": ["x"], "why_it_matters": ["y"],
            "who_should_care": ["z"], "significance_score": 1.0, "significance_level": "minimal",
        },
    )
    scored_diff = {"items": [], "overall_score": 87.5, "overall_level": "very_high"}
    result = run_change_analysis(scored_diff, {"brand": "B", "name": "N", "category": "protein_powder"})
    assert result["significance_score"] == 87.5
    assert result["significance_level"] == "very_high"


def test_health_context_disclaimer_enforced(monkeypatch):
    """The non-medical disclaimer is enforced even if the LLM omits it."""
    monkeypatch.setattr(
        "app.agents.health_context_agent.run_agent_json",
        lambda *a, **k: {"contexts": [{"audience": "general_consumers", "statement": "ok",
                                       "evidence_level": "label_comparison"}]},
    )
    result = run_health_context({"items": []}, {})
    assert "not medical advice" in result["disclaimer"]


def test_mock_change_analysis_structure():
    from app.services.comparison.significance_scoring import score_diff

    diff = score_diff({"items": [
        {"type": "allergen_added", "field": "soy", "presence_type": "contains",
         "detail": "Allergen disclosure added: soy (contains)"},
    ]}, "protein_bar")
    result = run_change_analysis(diff, {"brand": "NutriCrunch", "name": "Bar", "category": "protein_bar"})
    for key in ("summary", "what_changed", "why_it_matters", "who_should_care",
                "significance_score", "facts_vs_interpretation", "disclaimer"):
        assert key in result
    assert "People with food allergies" in result["who_should_care"]


def test_agent_json_strips_markdown_fences():
    assert adk_runtime._strip_json_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert json.loads(adk_runtime._strip_json_fences('{"a": 1}')) == {"a": 1}
