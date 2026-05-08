# RUNBOOK.md — Drift Triage Co-Pilot

This runbook explains how to run, test, debug, and demo the Drift Triage Co-Pilot system.

---

## 1. Prerequisites

Install:

```text
Docker Desktop
Git
Python 3.11+


Recommended Local Tools:
VS Code
PowerShell or Git Bash

2.Clone the Repository
git clone https://github.com/aliasfahani/week-5-DRIFT-TRIAGE-CO-PILOT.git
cd week-5-DRIFT-TRIAGE-CO-PILOT

3. Environment Setup

Copy the example environment file.

Linux / macOS / Git Bash
cp .env.example .env

Check .env and fill any required values.

Windows PowerShell

Copy-Item .env.example .env

Typical values:

MODEL_API_PORT=8000
AGENT_API_PORT=8001
DASHBOARD_PORT=8501

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=drift_triage
POSTGRES_USER=drift_user
POSTGRES_PASSWORD=drift_password

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

If MLflow is enabled, also check:

MLFLOW_TRACKING_URI
MLFLOW_EXPERIMENT_NAME
4. Start the Full Stack with Docker Compose

From the repository root:

docker compose up --build

This should start:

model_api
agent_api
dashboard
worker
postgres
redis

Expected URLs:

Model API: http://localhost:8000/docs
Agent API: http://localhost:8001/docs
Dashboard: http://localhost:8501
5. Stop the Stack

Press:

CTRL + C

Then run:

docker compose down

To remove volumes and reset state:

docker compose down -v

Warning: -v removes persistent volumes such as Postgres and Redis data.

6. Local Development Without Docker

Create a virtual environment:

python -m venv .venv

Activate it.

Windows PowerShell
.venv\Scripts\Activate.ps1
Git Bash
source .venv/Scripts/activate

Install dependencies:

pip install -e ".[dev]"

Train or refresh model artifacts:

python -m services.model_api.app.ml.train

Run model API:

python -m uvicorn services.model_api.app.main:app --reload --port 8000

Run agent API:

python -m uvicorn services.agent_api.app.main:app --reload --port 8001

Run dashboard:

streamlit run dashboard/app.py
7. Service Health Checks
Model API

Open:

http://localhost:8000/health

Expected:

{
  "status": "ok",
  "model_loaded": true
}

If model_loaded is false, run:

python -m services.model_api.app.ml.train

Then restart the model API.

Agent API

Open:

http://localhost:8001/health

Expected:

{
  "status": "ok",
  "service": "agent_api"
}
Dashboard

Open:

http://localhost:8501
8. Prediction Test

Open:

http://localhost:8000/docs

Call:

POST /predict

Sample request:

{
  "age": 35,
  "job": "admin.",
  "marital": "married",
  "education": "university.degree",
  "default": "no",
  "housing": "yes",
  "loan": "no",
  "contact": "cellular",
  "month": "may",
  "day_of_week": "mon",
  "campaign": 1,
  "pdays": 999,
  "previous": 0,
  "poutcome": "nonexistent",
  "emp.var.rate": 1.1,
  "cons.price.idx": 93.994,
  "cons.conf.idx": -36.4,
  "euribor3m": 4.857,
  "nr.employed": 5191.0
}

Expected response shape:

{
  "probability": 0.123,
  "prediction": 0,
  "threshold": 0.3845233329570477,
  "model_name": "bank_marketing_classifier",
  "model_version": "local-artifact"
}

Exact probability may differ depending on model artifacts.

9. Drift Report Test

After sending some predictions, call:

GET /drift/report

or:

GET /drift/report?window_size=100

Expected response shape:

{
  "severity": "low",
  "window_size": 10,
  "numeric_drift": {},
  "categorical_drift": {},
  "output_drift": {}
}

With very few predictions, drift values may look high. This is expected because drift windows are more meaningful with more traffic.

10. Trigger Drift Notification

Call:

POST /drift/check-and-notify

Expected behavior:

Model API generates a drift report.
It checks if severity changed.
If severity changed, it sends a webhook to the Agent API.
Agent API opens an investigation.

Possible response:

{
  "drift_report": {
    "severity": "high"
  },
  "notification": {
    "notified": true,
    "reason": "severity_changed",
    "agent_response": {
      "status": "accepted",
      "investigation_id": "inv-drift-event-..."
    }
  }
}

If response says:

{
  "notified": false,
  "reason": "severity_unchanged"
}

then the severity did not change from the previous run.

To force a new notification in local dev, delete:

runtime/last_drift_severity.json

Then call /drift/check-and-notify again.

11. Agent Investigation Test

Open:

http://localhost:8001/docs

Call:

GET /investigations

Expected response includes:

investigation_id
severity
status
triage_summary
action_recommendation
comms_summary
trajectory

Expected trajectory:

supervisor → triage → action → comms

If there is no trajectory, verify that the Agent API is running the LangGraph flow and not the old basic investigation builder.

12. Human Approval Test

Call:

GET /approvals/pending

If the investigation recommends:

retrain_candidate
rollback_candidate

then it should appear in the pending approval inbox.

To approve:

POST /approvals/{investigation_id}/approve

Sample request:

{
  "approved_by": "muhammad",
  "note": "Approved for demo testing."
}

Expected response:

{
  "status": "approved",
  "investigation": {
    "status": "approved"
  },
  "queue_dispatch": {}
}

After approval, actions should be enqueued in Redis.

13. Queue Status Test

Call:

GET /queue/status

Expected response shape:

{
  "main_queue_depth": 0,
  "retry_queue_depth": 0,
  "dlq_depth": 0
}

After approval, queue depth may briefly increase until the worker consumes the job.

14. Worker Test

The worker should automatically consume approved jobs from Redis.

Expected action flow:

approval
→ enqueue action
→ worker consumes job
→ worker executes action
→ if Production-impacting, worker calls model API /registry/promote

Check worker logs:

docker compose logs -f worker
15. Registry State Test

Call:

GET /registry/state

Expected response shape:

{
  "production": {},
  "history": []
}

After a successful approved promotion action, production and/or history should update.

To manually inspect promotion behavior, call:

POST /registry/promote

But normally this should be called by the worker after human approval.

16. Dashboard Demo Flow

Open:

http://localhost:8501

Use dashboard pages:

Service Health
model API health
agent API health
Drift Report
refresh drift report
trigger drift notification
Investigations
see investigations
inspect trajectory
inspect action recommendations
Human Approval Inbox
approve/reject pending actions
Queue Status
check main queue, retry queue, DLQ
Registry State
verify Production state/history
