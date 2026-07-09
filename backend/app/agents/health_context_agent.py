"""HealthContextAgent: audience-specific, realistic health context for label changes."""
import json

from app.agents.adk_runtime import load_prompt, model_label, run_agent_json
from app.services.analysis.risk_rules import DISCLAIMER, build_health_context

PROMPT_FILE = "health_context_prompt.md"


def build_agent():
    from google.adk.agents import LlmAgent

    from app.config import get_settings

    instruction, _ = load_prompt(PROMPT_FILE)
    return LlmAgent(
        name="health_context_agent",
        model=get_settings().gemini_model,
        description="Provides realistic, audience-specific consumer health context for label changes.",
        instruction=instruction,
    )


def run_health_context(scored_diff: dict, product_context: dict) -> dict:
    """Health context for a scored diff, always carrying the non-medical disclaimer."""
    instruction, version = load_prompt(PROMPT_FILE)
    deterministic = build_health_context(scored_diff)

    payload = run_agent_json(
        "health_context_agent", instruction,
        json.dumps({
            "scored_diff": scored_diff,
            "product_context": product_context,
            "rule_generated_contexts": deterministic["contexts"],
        }),
    )
    if payload is not None and "contexts" in payload:
        payload["disclaimer"] = DISCLAIMER  # enforce, never trust the LLM to include it
        result = payload
        model = model_label()
    else:
        result = deterministic
        model = "mock-rule-based"
    result["model_name"] = model
    result["prompt_version"] = version
    return result
