"""Temporary investigation store.

This is a JSONL store for the early integration stage.
Later, this should move to Postgres + LangGraph checkpoints.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime")
INVESTIGATION_LOG_PATH = RUNTIME_DIR / "agent_investigations.jsonl"


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def save_investigation(investigation: dict[str, Any]) -> None:
    """Append investigation state to JSONL log."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    with INVESTIGATION_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(investigation) + "\n")


def _read_all_versions() -> list[dict[str, Any]]:
    """Read all investigation versions from the JSONL log."""
    if not INVESTIGATION_LOG_PATH.exists():
        return []

    investigations: list[dict[str, Any]] = []

    with INVESTIGATION_LOG_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                investigations.append(json.loads(line))

    return investigations


def list_investigations() -> list[dict[str, Any]]:
    """Return the latest state per investigation."""
    latest_by_id: dict[str, dict[str, Any]] = {}

    for investigation in _read_all_versions():
        investigation_id = investigation["investigation_id"]
        latest_by_id[investigation_id] = investigation

    return list(latest_by_id.values())


def get_investigation(investigation_id: str) -> dict[str, Any] | None:
    """Get the latest version of one investigation."""
    for investigation in list_investigations():
        if investigation["investigation_id"] == investigation_id:
            return investigation

    return None


def list_pending_approvals() -> list[dict[str, Any]]:
    """List investigations waiting for human approval."""
    return [
        investigation
        for investigation in list_investigations()
        if investigation.get("status") == "pending_human_approval"
    ]


def approve_investigation(
    *,
    investigation_id: str,
    approved_by: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    """Approve a pending investigation."""
    investigation = get_investigation(investigation_id)

    if investigation is None:
        return None

    updated = {
        **investigation,
        "status": "approved",
        "approved_by": approved_by,
        "approval_note": note,
        "approved_at": utc_now_iso(),
    }

    save_investigation(updated)
    return updated


def reject_investigation(
    *,
    investigation_id: str,
    rejected_by: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    """Reject a pending investigation."""
    investigation = get_investigation(investigation_id)

    if investigation is None:
        return None

    updated = {
        **investigation,
        "status": "rejected",
        "rejected_by": rejected_by,
        "rejection_note": note,
        "rejected_at": utc_now_iso(),
    }

    save_investigation(updated)
    return updated