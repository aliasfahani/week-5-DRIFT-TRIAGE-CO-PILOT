"""Prompt loading utilities.

Prompts are stored as version-controlled files under /prompts.
"""

from __future__ import annotations

from pathlib import Path


PROMPT_DIR = Path("prompts")


def load_prompt(prompt_name: str) -> str:
    """Load a prompt file by name."""
    path = PROMPT_DIR / prompt_name

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    return path.read_text(encoding="utf-8")


def load_all_prompts() -> dict[str, str]:
    """Load all agent prompts."""
    return {
        "triage": load_prompt("triage_agent.md"),
        "action": load_prompt("action_agent.md"),
        "comms": load_prompt("comms_agent.md"),
    }