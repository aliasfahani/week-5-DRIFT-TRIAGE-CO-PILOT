"""Webhook utilities for notifying the agent about drift severity changes."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

LAST_SEVERITY_PATH = Path("runtime/last_drift_severity.json")

DEFAULT_AGENT_WEBHOOK_URL = "http://127.0.0.1:8001/webhooks/drift"


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def load_last_severity() -> str | None:
    """Load the last drift severity sent to the agent."""
    if not LAST_SEVERITY_PATH.exists():
        return None

    payload = json.loads(LAST_SEVERITY_PATH.read_text(encoding="utf-8"))
    return payload.get("last_severity")


def save_last_severity(severity: str) -> None:
    """Persist the last drift severity."""
    LAST_SEVERITY_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "last_severity": severity,
        "updated_at": utc_now_iso(),
    }

    LAST_SEVERITY_PATH.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def extract_drifted_features(drift_report: dict[str, Any]) -> list[str]:
    """Extract non-low drifted features from the drift report."""
    drifted_features: list[str] = []

    for feature, result in drift_report.get("numeric_drift", {}).items():
        if result.get("severity") in {"medium", "high"}:
            drifted_features.append(feature)

    for feature, result in drift_report.get("categorical_drift", {}).items():
        if result.get("severity") in {"medium", "high"}:
            drifted_features.append(feature)

    output_severity = drift_report.get("output_drift", {}).get("severity")
    if output_severity in {"medium", "high"}:
        drifted_features.append("model_output_distribution")

    return drifted_features


def recommend_actions(severity: str, drifted_features: list[str]) -> list[str]:
    """Recommend next actions based on drift severity."""
    if severity == "low":
        return ["no_action"]

    if severity == "medium":
        return ["replay_test_set"]

    if severity == "high":
        actions = ["replay_test_set", "retrain_candidate"]

        if "model_output_distribution" in drifted_features:
            actions.append("rollback_candidate")

        return actions

    return ["no_action"]


def build_drift_event(
    *,
    drift_report: dict[str, Any],
    previous_severity: str | None,
) -> dict[str, Any]:
    """Build the DriftEvent contract payload."""
    event_uuid = uuid.uuid4().hex[:12]
    created_at = utc_now_iso()

    severity = drift_report["severity"]
    drifted_features = extract_drifted_features(drift_report)

    return {
        "contract_version": "v1",
        "event_id": f"drift-event-{event_uuid}",
        "report_id": f"drift-report-{event_uuid}",
        "model_name": "bank_marketing_classifier",
        "model_version": "local-artifact",
        "severity": severity,
        "previous_severity": previous_severity,
        "drifted_features": drifted_features,
        "recommended_actions": recommend_actions(severity, drifted_features),
        "created_at": created_at,
        "drift_report": drift_report,
    }


async def send_drift_webhook(event: dict[str, Any]) -> dict[str, Any]:
    """Send drift event to the agent webhook endpoint."""
    webhook_url = os.getenv("AGENT_WEBHOOK_URL", DEFAULT_AGENT_WEBHOOK_URL)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json=event)
        response.raise_for_status()
        return response.json()


async def notify_agent_if_severity_changed(
    *,
    drift_report: dict[str, Any],
) -> dict[str, Any]:
    """Notify the agent only if drift severity changed."""
    current_severity = drift_report["severity"]
    previous_severity = load_last_severity()

    if previous_severity == current_severity:
        return {
            "notified": False,
            "reason": "severity_unchanged",
            "current_severity": current_severity,
            "previous_severity": previous_severity,
        }

    event = build_drift_event(
        drift_report=drift_report,
        previous_severity=previous_severity,
    )

    try:
        agent_response = await send_drift_webhook(event)
    except httpx.HTTPError as exc:
        return {
            "notified": False,
            "reason": "agent_webhook_failed",
            "error": str(exc),
            "event": event,
        }

    save_last_severity(current_severity)

    return {
        "notified": True,
        "reason": "severity_changed",
        "previous_severity": previous_severity,
        "current_severity": current_severity,
        "event": event,
        "agent_response": agent_response,
    }