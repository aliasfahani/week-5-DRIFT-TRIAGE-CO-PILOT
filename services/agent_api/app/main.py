"""FastAPI application for the drift triage agent service."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.agent_api.app.graph.graph import run_drift_triage
from services.agent_api.app.queue import enqueue_action, queue_status
from services.agent_api.app.schemas import DriftEvent, DriftWebhookResponse
from services.agent_api.app.store import (
    approve_investigation,
    get_investigation,
    list_investigations,
    list_pending_approvals,
    reject_investigation,
    save_investigation,
)

app = FastAPI(
    title="Drift Triage Co-Pilot Agent API",
    version="0.1.0",
    description="Receives drift events and runs the LangGraph triage supervisor.",
)


class ApprovalRequest(BaseModel):
    """Human approval request."""

    approved_by: str
    note: str | None = None


class RejectionRequest(BaseModel):
    """Human rejection request."""

    rejected_by: str
    note: str | None = None


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "agent_api",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Health endpoint."""
    return {
        "status": "ok",
        "service": "agent_api",
    }


@app.post("/webhooks/drift", response_model=DriftWebhookResponse)
def receive_drift_webhook(event: DriftEvent):
    """Receive drift event, run supervisor graph, and save investigation."""
    final_state = run_drift_triage(event)
    save_investigation(dict(final_state))

    return DriftWebhookResponse(
        status="accepted",
        investigation_id=final_state["investigation_id"],
    )


@app.get("/investigations")
def investigations():
    """List all latest investigations."""
    items = list_investigations()

    return {
        "count": len(items),
        "items": items,
    }


@app.get("/investigations/{investigation_id}")
def investigation_detail(investigation_id: str):
    """Get one investigation by ID."""
    investigation = get_investigation(investigation_id)

    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    return investigation


@app.get("/approvals/pending")
def pending_approvals():
    """List investigations pending human approval."""
    items = list_pending_approvals()

    return {
        "count": len(items),
        "items": items,
    }


@app.get("/queue/status")
def queue_depth():
    """Return queue and DLQ depths."""
    try:
        return queue_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Queue status failed: {exc}") from exc


@app.post("/approvals/{investigation_id}/approve")
def approve(
    investigation_id: str,
    request: ApprovalRequest,
):
    """Approve a pending investigation."""
    updated = approve_investigation(
        investigation_id=investigation_id,
        approved_by=request.approved_by,
        note=request.note,
    )

    if updated is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    enqueue_results = []
    for action in updated.get("action_recommendation", []):
        if action == "no_action":
            continue
        enqueue_results.append(
            enqueue_action(
                investigation_id=investigation_id,
                action=action,
                payload={
                    "approved_by": request.approved_by,
                    "approval_note": request.note,
                },
            )
        )

    return {
        "status": "approved",
        "investigation": updated,
        "queue_dispatch": enqueue_results,
    }


@app.post("/approvals/{investigation_id}/reject")
def reject(
    investigation_id: str,
    request: RejectionRequest,
):
    """Reject a pending investigation."""
    updated = reject_investigation(
        investigation_id=investigation_id,
        rejected_by=request.rejected_by,
        note=request.note,
    )

    if updated is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    return {
        "status": "rejected",
        "investigation": updated,
    }