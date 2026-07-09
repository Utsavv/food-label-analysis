"""IngredientExplainerAgent: plain-English ingredient explanations."""
import json

from app.agents.adk_runtime import load_prompt, model_label, run_agent_json
from app.services.analysis.plain_english import explain_ingredient_deterministic
from app.services.analysis.risk_rules import DISCLAIMER

PROMPT_FILE = "ingredient_explanation_prompt.md"

_REQUIRED_KEYS = {"ingredient_name", "plain_english_meaning", "common_use", "commonness",
                  "health_context", "confidence"}


def build_agent():
    from google.adk.agents import LlmAgent

    from app.config import get_settings

    instruction, _ = load_prompt(PROMPT_FILE)
    return LlmAgent(
        name="ingredient_explainer_agent",
        model=get_settings().gemini_model,
        description="Explains confusing food ingredients in plain English for Indian consumers.",
        instruction=instruction,
    )


def run_ingredient_explainer(ingredient_name: str, category: str = "protein_powder") -> dict:
    """Explain an ingredient. Gemini when configured, glossary otherwise."""
    instruction, version = load_prompt(PROMPT_FILE)
    payload = run_agent_json(
        "ingredient_explainer_agent", instruction,
        json.dumps({"ingredient_name": ingredient_name, "product_category": category}),
    )
    if payload is not None and _REQUIRED_KEYS.issubset(payload):
        payload.setdefault("disclaimer", DISCLAIMER)
        result = payload
        model = model_label()
    else:
        result = explain_ingredient_deterministic(ingredient_name, category)
        model = "mock-rule-based"
    result["model_name"] = model
    result["prompt_version"] = version
    return result
