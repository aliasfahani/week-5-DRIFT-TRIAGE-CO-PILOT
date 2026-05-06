"""FastAPI application for the drift triage agent service."""

from __future__ import annotations

from fastapi import FastAPI

from services.agent_api.app.schemas import DriftEvent, DriftWebhookResponse
from services.agent_api.app.store import (
    build_investigation,
    list_investigations,
    save_investigation,
)

app = FastAPI(
    title="Drift Triage Co-Pilot Agent API",
    version="0.1.0",
    description="Receives drift events and opens agent investigations.",
)


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
    """Receive drift event from the model platform and open an investigation."""
    investigation = build_investigation(event)
    save_investigation(investigation)

    return DriftWebhookResponse(
        status="accepted",
        investigation_id=investigation["investigation_id"],
    )


@app.get("/investigations")
def investigations():
    """List all investigations received so far."""
    return {
        "count": len(list_investigations()),
        "items": list_investigations(),
    }