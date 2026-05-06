"""LangGraph workflow definition for the drift triage supervisor."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.agent_api.app.graph.nodes import (
    action_node,
    comms_node,
    supervisor_node,
    triage_node,
)
from services.agent_api.app.graph.state import DriftTriageState
from services.agent_api.app.schemas import DriftEvent


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
    """Run the full drift triage graph for one event."""
    graph = build_drift_triage_graph()
    initial_state = event_to_initial_state(event)
    final_state = graph.invoke(initial_state)
    return final_state