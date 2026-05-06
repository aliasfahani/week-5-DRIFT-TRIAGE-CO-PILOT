"""Streamlit dashboard for Drift Triage Co-Pilot."""

from __future__ import annotations

import os

import requests
import streamlit as st


MODEL_API_URL = os.getenv("MODEL_API_URL", "http://127.0.0.1:8000")
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8001")


st.set_page_config(
    page_title="Drift Triage Co-Pilot",
    page_icon="🧭",
    layout="wide",
)

st.title("🧭 Drift Triage Co-Pilot Dashboard")
st.caption("Model monitoring, drift investigations, and human approvals.")


def get_json(url: str):
    """Fetch JSON from an API endpoint."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"error": str(exc)}


def post_json(url: str, payload: dict):
    """POST JSON to an API endpoint."""
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"error": str(exc)}


page = st.sidebar.radio(
    "Navigation",
    [
        "Service Health",
        "Drift Report",
        "Investigations",
        "Human Approval Inbox",
    ],
)


if page == "Service Health":
    st.header("Service Health")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Model API")
        st.json(get_json(f"{MODEL_API_URL}/health"))

    with col2:
        st.subheader("Agent API")
        st.json(get_json(f"{AGENT_API_URL}/health"))


elif page == "Drift Report":
    st.header("Current Drift Report")

    window_size = st.slider("Window size", min_value=1, max_value=500, value=100)

    if st.button("Refresh drift report"):
        report = get_json(f"{MODEL_API_URL}/drift/report?window_size={window_size}")
        st.json(report)

    st.divider()

    if st.button("Check drift and notify agent"):
        result = post_json(
            f"{MODEL_API_URL}/drift/check-and-notify?window_size={window_size}",
            payload={},
        )
        st.json(result)


elif page == "Investigations":
    st.header("Agent Investigations")

    data = get_json(f"{AGENT_API_URL}/investigations")

    if "error" in data:
        st.error(data["error"])
    else:
        st.metric("Total investigations", data.get("count", 0))

        for item in data.get("items", []):
            with st.expander(
                f"{item.get('investigation_id')} — {item.get('severity')} — {item.get('status')}"
            ):
                st.write("**Model:**", item.get("model_name"))
                st.write("**Version:**", item.get("model_version"))
                st.write("**Drift type:**", item.get("drift_type"))
                st.write("**Triage summary:**", item.get("triage_summary"))
                st.write("**Recommended actions:**", item.get("action_recommendation"))
                st.write("**Needs human approval:**", item.get("needs_human_approval"))
                st.write("**Comms summary:**", item.get("comms_summary"))
                st.write("**Trajectory:**", " → ".join(item.get("trajectory", [])))
                st.json(item)


elif page == "Human Approval Inbox":
    st.header("Human Approval Inbox")

    data = get_json(f"{AGENT_API_URL}/approvals/pending")

    if "error" in data:
        st.error(data["error"])
    else:
        st.metric("Pending approvals", data.get("count", 0))

        for item in data.get("items", []):
            investigation_id = item.get("investigation_id")

            with st.expander(f"Pending: {investigation_id}"):
                st.write("**Severity:**", item.get("severity"))
                st.write("**Recommended actions:**", item.get("action_recommendation"))
                st.write("**Summary:**", item.get("comms_summary"))

                operator_name = st.text_input(
                    "Your name",
                    value="muhammad",
                    key=f"name-{investigation_id}",
                )

                note = st.text_area(
                    "Approval/rejection note",
                    key=f"note-{investigation_id}",
                )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Approve", key=f"approve-{investigation_id}"):
                        result = post_json(
                            f"{AGENT_API_URL}/approvals/{investigation_id}/approve",
                            {
                                "approved_by": operator_name,
                                "note": note,
                            },
                        )
                        st.success("Approved")
                        st.json(result)

                with col2:
                    if st.button("Reject", key=f"reject-{investigation_id}"):
                        result = post_json(
                            f"{AGENT_API_URL}/approvals/{investigation_id}/reject",
                            {
                                "rejected_by": operator_name,
                                "note": note,
                            },
                        )
                        st.warning("Rejected")
                        st.json(result)