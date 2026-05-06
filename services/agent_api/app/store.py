"""Temporary investigation store.

This is a lightweight JSONL store for the early integration stage.
Later, this should move to Postgres + LangGraph checkpoints.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.agent_api.app.schemas import DriftEvent

RUNTIME_DIR = Path("runtime")
INVESTIGATION_LOG_PATH = RUNTIME_DIR / "agent_investigations.jsonl"


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def build_investigation(event: DriftEvent) -> dict[str, Any]:
    """Create an investigation record from a drift event."""
    investigation_id = f"inv-{event.event_id}"

    return {
        "investigation_id": investigation_id,
        "event_id": event.event_id,
        "report_id": event.report_id,
        "model_name": event.model_name,
        "model_version": event.model_version,
        "severity": event.severity,
        "previous_severity": event.previous_severity,
        "drifted_features": event.drifted_features,
        "recommended_actions": event.recommended_actions,
        "status": "open",
        "created_at": utc_now_iso(),
        "source_event_created_at": event.created_at,
        "needs_human_approval": any(
            action in {"retrain_candidate", "rollback_candidate"}
            for action in event.recommended_actions
        ),
        "drift_report": event.drift_report,
    }


def save_investigation(investigation: dict[str, Any]) -> None:
    """Append investigation to JSONL log."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    with INVESTIGATION_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(investigation) + "\n")


def list_investigations() -> list[dict[str, Any]]:
    """Read all saved investigations."""
    if not INVESTIGATION_LOG_PATH.exists():
        return []

    investigations: list[dict[str, Any]] = []

    with INVESTIGATION_LOG_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                investigations.append(json.loads(line))

    return investigations