"""State definition for the drift triage LangGraph workflow."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


Severity = Literal["low", "medium", "high"]
InvestigationStatus = Literal[
    "open",
    "pending_human_approval",
    "approved",
    "rejected",
    "resolved",
]


class DriftTriageState(TypedDict, total=False):
    """Shared state passed between supervisor, triage, action, and comms nodes."""

    # Original webhook event fields
    event_id: str
    report_id: str
    model_name: str
    model_version: str
    severity: Severity
    previous_severity: Severity | None
    drifted_features: list[str]
    recommended_actions: list[str]
    created_at: str
    drift_report: dict[str, Any]

    # Investigation fields
    investigation_id: str
    status: InvestigationStatus
    needs_human_approval: bool

    # Agent outputs
    supervisor_decision: str
    triage_summary: str
    drift_type: str
    action_recommendation: list[str]
    comms_summary: str

    # Trajectory for future snapshot testing
    trajectory: list[str]