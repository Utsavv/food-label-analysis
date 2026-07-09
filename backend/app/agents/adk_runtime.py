"""Google ADK runtime helpers.

Demo mode ("mock" provider, the default) needs neither google-adk nor an API
key: every agent has a deterministic fallback. With LLM_PROVIDER=google and a
GOOGLE_API_KEY, agents run as ADK LlmAgents on Gemini.
"""
import json
import logging
import re
import uuid
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_VERSION_RE = re.compile(r"PROMPT_VERSION:\s*(\S+)")


def load_prompt(filename: str) -> tuple[str, str]:
    """Return (instruction_text, prompt_version) for a versioned prompt file."""
    text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    m = _VERSION_RE.search(text)
    version = m.group(1).rstrip("->").strip() if m else "unknown"
    return text, version


def adk_available() -> bool:
    settings = get_settings()
    if settings.llm_provider != "google" or not settings.google_api_key:
        return False
    try:
        import google.adk  # noqa: F401

        return True
    except ImportError:
        logger.warning("LLM_PROVIDER=google but google-adk is not installed; using mock agents")
        return False


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def run_agent_json(agent_name: str, instruction: str, user_message: str) -> dict | None:
    """Run a single-turn ADK LlmAgent and parse its JSON reply.

    Returns None when ADK/Gemini is unavailable or the reply is not valid
    JSON — callers must fall back to their deterministic implementation.
    """
    if not adk_available():
        return None
    settings = get_settings()
    import os

    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)

    try:
        from google.adk.agents import LlmAgent
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        agent = LlmAgent(name=agent_name, model=settings.gemini_model, instruction=instruction)
        runner = InMemoryRunner(agent=agent, app_name="labelwatch")
        session_id = uuid.uuid4().hex
        import asyncio

        async def _run() -> str:
            await runner.session_service.create_session(
                app_name="labelwatch", user_id="pipeline", session_id=session_id
            )
            reply = ""
            async for event in runner.run_async(
                user_id="pipeline",
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=user_message)]),
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            reply += part.text
            return reply

        raw = asyncio.run(_run())
        return json.loads(_strip_json_fences(raw))
    except Exception as exc:
        logger.warning("ADK agent %s failed (%s); falling back to deterministic output", agent_name, exc)
        return None


def model_label() -> str:
    settings = get_settings()
    if adk_available():
        return settings.gemini_model
    return "mock-rule-based"
