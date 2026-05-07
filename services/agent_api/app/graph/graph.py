"""LangGraph workflow definition for the drift triage supervisor."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.agent_api.app.graph.nodes import (
    NODE_FUNCTIONS,
    action_node,
    comms_node,
    supervisor_node,
    triage_node,
)
from services.agent_api.app.graph.state import DriftTriageState
from services.agent_api.app.schemas import DriftEvent
from services.agent_api.app.store import get_latest_checkpoint, save_checkpoint

ORDERED_NODES = ("supervisor", "triage", "action", "comms")


def build_drift_triage_graph():
    """Build and compile the drift triage LangGraph workflow."""
    workflow = StateGraph(DriftTriageState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("action", action_node)
    workflow.add_node("comms", comms_node)

    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "triage")
    workflow.add_edge("triage", "action")
    workflow.add_edge("action", "comms")
    workflow.add_edge("comms", END)

    return workflow.compile()


def event_to_initial_state(event: DriftEvent) -> DriftTriageState:
    """Convert a DriftEvent into initial graph state."""
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
        "created_at": event.created_at,
        "drift_report": event.drift_report,
        "trajectory": [],
        "status": "open",
        "needs_human_approval": False,
    }


def run_drift_triage(event: DriftEvent) -> DriftTriageState:
    """Run drift triage with durable checkpoints and resume support."""
    initial_state = event_to_initial_state(event)
    investigation_id = initial_state["investigation_id"]
    latest_checkpoint = get_latest_checkpoint(investigation_id)

    if latest_checkpoint is None:
        graph = build_drift_triage_graph()
        final_state: DriftTriageState = initial_state

        save_checkpoint(
            investigation_id=investigation_id,
            node_name="start",
            state=dict(initial_state),
        )

        for state in graph.stream(initial_state, stream_mode="values"):
            final_state = state
            trajectory = state.get("trajectory", [])
            current_node = trajectory[-1] if trajectory else "start"
            save_checkpoint(
                investigation_id=investigation_id,
                node_name=current_node,
                state=dict(state),
            )

        return final_state

    resumed_state = latest_checkpoint.get("state", initial_state)
    completed_nodes = len(resumed_state.get("trajectory", []))
    remaining_nodes = ORDERED_NODES[completed_nodes:]

    state: DriftTriageState = resumed_state
    for node_name in remaining_nodes:
        state = NODE_FUNCTIONS[node_name](state)
        save_checkpoint(
            investigation_id=investigation_id,
            node_name=node_name,
            state=dict(state),
        )

    return state