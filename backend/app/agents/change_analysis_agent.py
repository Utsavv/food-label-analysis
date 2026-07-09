"""ChangeAnalysisAgent: plain-English explanation of a deterministic scored diff."""
import json

from app.agents.adk_runtime import load_prompt, model_label, run_agent_json
from app.services.analysis.plain_english import generate_change_report

PROMPT_FILE = "change_analysis_prompt.md"

_REQUIRED_KEYS = {"summary", "what_changed", "why_it_matters", "who_should_care"}


def build_agent():
    from google.adk.agents import LlmAgent

    from app.config import get_settings

    instruction, _ = load_prompt(PROMPT_FILE)
    return LlmAgent(
        name="change_analysis_agent",
        model=get_settings().gemini_model,
        description="Explains label-diff JSON in plain English: what changed, why it matters, who should care.",
        instruction=instruction,
    )


def run_change_analysis(scored_diff: dict, product_context: dict) -> dict:
    """Analyze a scored diff. Returns analysis dict with model/prompt metadata.

    The deterministic report is always computed; the LLM (when configured)
    rewrites it with the same facts. Fact fields the LLM cannot be trusted
    with (scores) are always taken from the deterministic side.
    """
    instruction, version = load_prompt(PROMPT_FILE)
    deterministic = generate_change_report(scored_diff, product_context)

    payload = run_agent_json(
        "change_analysis_agent", instruction,
        json.dumps({"scored_diff": scored_diff, "product_context": product_context}),
    )
    if payload is not None and _REQUIRED_KEYS.issubset(payload):
        payload["significance_score"] = scored_diff.get("overall_score", 0.0)
        payload["significance_level"] = scored_diff.get("overall_level", "none")
        payload.setdefault("disclaimer", deterministic["disclaimer"])
        result = payload
        model = model_label()
    else:
        result = deterministic
        model = "mock-rule-based"
    result["model_name"] = model
    result["prompt_version"] = version
    return result
