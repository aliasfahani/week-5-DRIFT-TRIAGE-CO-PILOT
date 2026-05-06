"""Pydantic schemas for the agent API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high"]
RecommendedAction = Literal[
    "no_action",
    "replay_test_set",
    "retrain_candidate",
    "rollback_candidate",
]


class DriftEvent(BaseModel):
    """Contract payload sent from model platform to agent."""

    contract_version: Literal["v1"]
    event_id: str
    report_id: str
    model_name: str
    model_version: str
    severity: Severity
    previous_severity: Severity | None = None
    drifted_features: list[str] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    created_at: str
    drift_report: dict[str, Any]


class DriftWebhookResponse(BaseModel):
    """Response returned after accepting a drift webhook."""

    status: str
    investigation_id: str