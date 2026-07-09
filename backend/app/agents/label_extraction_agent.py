"""LabelExtractionAgent: turns messy OCR/web text into strict StructuredLabel JSON.

The deterministic parser runs first; the agent is consulted when the parser's
confidence is low (messy OCR). Agent output is validated against the schema —
invalid output is discarded in favour of the deterministic parse.
"""
import logging

from pydantic import ValidationError

from app.agents.adk_runtime import load_prompt, run_agent_json
from app.schemas import StructuredLabel
from app.services.extraction.label_parser import parse_label_text

logger = logging.getLogger(__name__)

PROMPT_FILE = "extraction_prompt.md"
CONFIDENCE_THRESHOLD = 0.5  # below this, ask the LLM to assist


def build_agent():
    """ADK LlmAgent for use with `adk web` / the root agent."""
    from google.adk.agents import LlmAgent

    from app.config import get_settings

    instruction, _ = load_prompt(PROMPT_FILE)
    return LlmAgent(
        name="label_extraction_agent",
        model=get_settings().gemini_model,
        description="Parses messy OCR/web label text into strict structured label JSON.",
        instruction=instruction,
    )


def run_extraction(raw_text: str) -> tuple[StructuredLabel, str, str]:
    """Extract a structured label. Returns (label, model_name, prompt_version)."""
    instruction, version = load_prompt(PROMPT_FILE)
    deterministic = parse_label_text(raw_text)

    if deterministic.overall_confidence >= CONFIDENCE_THRESHOLD:
        return deterministic, "deterministic-parser", version

    payload = run_agent_json(
        "label_extraction_agent", instruction,
        f"Extract the label from this text:\n\n{raw_text}",
    )
    if payload is not None:
        try:
            label = StructuredLabel.model_validate(payload)
            from app.agents.adk_runtime import model_label

            return label, model_label(), version
        except ValidationError as exc:
            logger.warning("LabelExtractionAgent returned invalid schema, using parser output: %s", exc)
    return deterministic, "deterministic-parser", version
