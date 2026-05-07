"""Rule-based supervisor, triage, action, and comms nodes.

This is the first LangGraph version.
Later, the rule-based logic can be replaced with LLM calls while keeping the same graph shape.
"""

from __future__ import annotations

from services.agent_api.app.graph.prompts import load_all_prompts
from services.agent_api.app.graph.state import DriftTriageState


def _append_trajectory(state: DriftTriageState, node_name: str) -> list[str]:
    """Append a node name to the trajectory list."""
    trajectory = list(state.get("trajectory", []))
    trajectory.append(node_name)
    return trajectory


def supervisor_node(state: DriftTriageState) -> DriftTriageState:
    """Supervisor node.

    The supervisor decides whether the event should be investigated.
    For now, all drift events become investigations.
    """
    severity = state.get("severity", "low")

    if severity == "low":
        decision = "investigate_low_priority"
    elif severity == "medium":
        decision = "investigate_medium_priority"
    else:
        decision = "investigate_high_priority"

    return {
        **state,
        "supervisor_decision": decision,
        "status": "open",
        "trajectory": _append_trajectory(state, "supervisor"),
    }


def triage_node(state: DriftTriageState) -> DriftTriageState:
    """Triage node.

    Identifies what kind of drift happened and creates a short triage summary.
    """
    load_all_prompts()  # proves prompts exist and are version-controlled

    drift_report = state.get("drift_report", {})

    numeric_drift = drift_report.get("numeric_drift", {})
    categorical_drift = drift_report.get("categorical_drift", {})
    output_drift = drift_report.get("output_drift", {})

    has_numeric = any(
        item.get("severity") in {"medium", "high"}
        for item in numeric_drift.values()
    )
    has_categorical = any(
        item.get("severity") in {"medium", "high"}
        for item in categorical_drift.values()
    )
    has_output = output_drift.get("severity") in {"medium", "high"}

    drift_types = []

    if has_numeric:
        drift_types.append("numeric")

    if has_categorical:
        drift_types.append("categorical")

    if has_output:
        drift_types.append("output")

    if not drift_types:
        drift_type = "none"
    elif len(drift_types) == 1:
        drift_type = drift_types[0]
    else:
        drift_type = "mixed"

    drifted_features = state.get("drifted_features", [])

    if drift_type == "none":
        summary = "No meaningful drift was detected in the current rolling window."
    else:
        summary = (
            f"{state.get('severity', 'low').title()} {drift_type} drift detected. "
            f"Drifted features: {', '.join(drifted_features) or 'not specified'}."
        )

    return {
        **state,
        "drift_type": drift_type,
        "triage_summary": summary,
        "trajectory": _append_trajectory(state, "triage"),
    }


def action_node(state: DriftTriageState) -> DriftTriageState:
    """Action node.

    Recommends the next operational action based on severity and drift type.
    """
    load_all_prompts()

    severity = state.get("severity", "low")
    drift_type = state.get("drift_type", "none")

    actions: list[str]

    if severity == "low":
        actions = ["no_action"]

    elif severity == "medium":
        actions = ["replay_test_set"]

    else:
        actions = ["replay_test_set", "retrain_candidate"]

        if drift_type in {"output", "mixed"}:
            actions.append("rollback_candidate")

    needs_human_approval = any(
        action in {"retrain_candidate", "rollback_candidate"}
        for action in actions
    )

    status = "pending_human_approval" if needs_human_approval else "resolved"

    return {
        **state,
        "action_recommendation": actions,
        "recommended_actions": actions,
        "needs_human_approval": needs_human_approval,
        "status": status,
        "trajectory": _append_trajectory(state, "action"),
    }


def comms_node(state: DriftTriageState) -> DriftTriageState:
    """Comms node.

    Creates a dashboard-friendly summary.
    """
    load_all_prompts()

    approval_text = (
        "Human approval is required before any Production-impacting action."
        if state.get("needs_human_approval")
        else "No human approval is required for the recommended action."
    )

    comms_summary = (
        f"Investigation {state.get('investigation_id')} opened for "
        f"{state.get('model_name')} version {state.get('model_version')}. "
        f"{state.get('triage_summary')} "
        f"Recommended actions: {', '.join(state.get('action_recommendation', []))}. "
        f"{approval_text}"
    )

    return {
        **state,
        "comms_summary": comms_summary,
        "trajectory": _append_trajectory(state, "comms"),
    }


NODE_FUNCTIONS = {
    "supervisor": supervisor_node,
    "triage": triage_node,
    "action": action_node,
    "comms": comms_node,
}