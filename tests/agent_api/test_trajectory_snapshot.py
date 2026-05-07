"""Regression tests for agent routing trajectories.

These tests intentionally avoid real LLM calls. The graph nodes are rule-based
and prompt loading is filesystem-backed, so CI can run without API keys.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.agent_api.app.graph.graph import run_drift_triage
from services.agent_api.app.schemas import DriftEvent

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_high_mixed_drift_trajectory_snapshot(monkeypatch):
    """High mixed drift should follow the expected node trajectory."""
    saved_checkpoints: list[dict] = []

    monkeypatch.setattr("services.agent_api.app.graph.graph.get_latest_checkpoint", lambda *_: None)
    monkeypatch.setattr(
        "services.agent_api.app.graph.graph.save_checkpoint",
        lambda **kwargs: saved_checkpoints.append(kwargs),
    )

    event = DriftEvent(
        contract_version="v1",
        event_id="drift-event-snapshot-1",
        report_id="drift-report-snapshot-1",
        model_name="bank_marketing_classifier",
        model_version="local-artifact",
        severity="high",
        previous_severity="medium",
        drifted_features=["euribor3m", "job", "model_output_distribution"],
        recommended_actions=["replay_test_set", "retrain_candidate", "rollback_candidate"],
        created_at="2026-05-07T12:00:00Z",
        drift_report={
            "numeric_drift": {"euribor3m": {"severity": "high"}},
            "categorical_drift": {"job": {"severity": "medium"}},
            "output_drift": {"severity": "high"},
        },
    )

    final_state = run_drift_triage(event)
    expected = _load_fixture("trajectory_high_mixed.json")

    snapshot = {
        "trajectory": final_state["trajectory"],
        "status": final_state["status"],
        "drift_type": final_state["drift_type"],
        "action_recommendation": final_state["action_recommendation"],
        "needs_human_approval": final_state["needs_human_approval"],
    }

    assert snapshot == expected
    assert len(saved_checkpoints) >= 5  # start + 4 nodes


def test_resume_from_checkpoint_continues_remaining_nodes(monkeypatch):
    """Resume should continue from saved trajectory state instead of restarting."""
    saved_checkpoints: list[dict] = []
    resumed = {
        "node_name": "triage",
        "state": {
            "investigation_id": "inv-drift-event-resume-1",
            "event_id": "drift-event-resume-1",
            "report_id": "drift-report-resume-1",
            "model_name": "bank_marketing_classifier",
            "model_version": "local-artifact",
            "severity": "medium",
            "previous_severity": "low",
            "drifted_features": ["euribor3m"],
            "recommended_actions": ["replay_test_set"],
            "created_at": "2026-05-07T12:00:00Z",
            "drift_report": {
                "numeric_drift": {"euribor3m": {"severity": "medium"}},
                "categorical_drift": {},
                "output_drift": {"severity": "low"},
            },
            "trajectory": ["supervisor", "triage"],
            "status": "open",
            "needs_human_approval": False,
            "drift_type": "numeric",
            "triage_summary": "Medium numeric drift detected.",
        },
        "created_at": "2026-05-07T12:00:00Z",
    }

    monkeypatch.setattr("services.agent_api.app.graph.graph.get_latest_checkpoint", lambda *_: resumed)
    monkeypatch.setattr(
        "services.agent_api.app.graph.graph.save_checkpoint",
        lambda **kwargs: saved_checkpoints.append(kwargs),
    )

    event = DriftEvent(
        contract_version="v1",
        event_id="drift-event-resume-1",
        report_id="drift-report-resume-1",
        model_name="bank_marketing_classifier",
        model_version="local-artifact",
        severity="medium",
        previous_severity="low",
        drifted_features=["euribor3m"],
        recommended_actions=["replay_test_set"],
        created_at="2026-05-07T12:00:00Z",
        drift_report={
            "numeric_drift": {"euribor3m": {"severity": "medium"}},
            "categorical_drift": {},
            "output_drift": {"severity": "low"},
        },
    )

    final_state = run_drift_triage(event)
    assert final_state["trajectory"] == ["supervisor", "triage", "action", "comms"]
    assert [item["node_name"] for item in saved_checkpoints] == ["action", "comms"]
