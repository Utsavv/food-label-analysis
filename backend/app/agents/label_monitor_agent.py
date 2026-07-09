"""LabelMonitorAgent: ADK orchestrator over the deterministic tool set.

Two ways to run a label check:

1. Deterministic pipeline (`app.services.label_check.run_label_check`) — used
   by the API and the weekly scheduler. Reliable, no LLM in the control loop.
2. This agent — the same tools driven by Gemini for interactive/agentic use
   (`adk web`), where a human asks it to check products, investigate failures,
   or explain results conversationally.

Per the architecture principle, production scheduling stays deterministic;
the agent adds reasoning on top of the identical tool functions.
"""
from app.agents.adk_runtime import load_prompt  # noqa: F401  (kept for symmetry)
from app.agents.tools import (
    compare_label_versions,
    create_comparison,
    explain_ingredient,
    fetch_manufacturer_page,
    generate_change_analysis,
    parse_label_text,
    run_ocr,
    save_label_version,
)

INSTRUCTION = """\
You are LabelMonitorAgent for LabelWatch India. You orchestrate checks of
packaged-food product labels (protein powders, protein bars and other
categories) from configured sources.

Workflow for a product check:
1. fetch_manufacturer_page(url, source_type) to get current label text.
2. If only images are available, run_ocr on downloaded images.
3. parse_label_text to obtain structured label JSON (deterministic).
4. save_label_version to persist it. If the returned version_hash matches the
   previous version, report "no change" and stop.
5. If the label changed: create_comparison, then compare_label_versions for
   the scored diff, then generate_change_analysis for the plain-English report.
6. Use explain_ingredient for any confusing new ingredient.

Rules:
- Never invent label data; only report what tools return.
- If a fetch fails, report the exact error and do not fabricate a label.
- Summaries must be plain English, direct about meaningful changes, and never
  presented as medical advice.
"""


def build_agent():
    from google.adk.agents import LlmAgent

    from app.config import get_settings

    return LlmAgent(
        name="label_monitor_agent",
        model=get_settings().gemini_model,
        description="Orchestrates product label checks: scrape, extract, version, compare, analyze.",
        instruction=INSTRUCTION,
        tools=[
            fetch_manufacturer_page,
            run_ocr,
            parse_label_text,
            save_label_version,
            create_comparison,
            compare_label_versions,
            generate_change_analysis,
            explain_ingredient,
        ],
    )
