"""Root agent wiring for `adk web` / `adk run`.

Exposes LabelMonitorAgent as the coordinator with the specialist agents as
sub-agents. Requires google-adk and a GOOGLE_API_KEY; the API/scheduler paths
never import this module.
"""


def build_root_agent():
    from google.adk.agents import LlmAgent

    from app.agents.change_analysis_agent import build_agent as build_change_analysis
    from app.agents.health_context_agent import build_agent as build_health_context
    from app.agents.ingredient_explainer_agent import build_agent as build_ingredient_explainer
    from app.agents.label_extraction_agent import build_agent as build_label_extraction
    from app.agents.label_monitor_agent import build_agent as build_label_monitor
    from app.config import get_settings

    monitor = build_label_monitor()
    return LlmAgent(
        name="labelwatch_root",
        model=get_settings().gemini_model,
        description="LabelWatch India coordinator: monitors food labels and explains changes.",
        instruction=(
            "You coordinate LabelWatch India. Route label-check and orchestration work to "
            "label_monitor_agent, messy text extraction to label_extraction_agent, ingredient "
            "questions to ingredient_explainer_agent, diff explanation to change_analysis_agent, "
            "and health questions about changes to health_context_agent. Answer in plain English "
            "and never give medical advice."
        ),
        sub_agents=[
            monitor,
            build_label_extraction(),
            build_ingredient_explainer(),
            build_change_analysis(),
            build_health_context(),
        ],
    )


try:  # `adk web` discovers module-level `root_agent`
    root_agent = build_root_agent()
except Exception:  # pragma: no cover - google-adk not installed / no key
    root_agent = None
