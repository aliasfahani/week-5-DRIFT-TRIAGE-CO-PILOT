# Week 5 Drift Triage Co-Pilot

A self-healing MLOps + agentic workflow project for the AIE Program Week 5 assignment.

This project trains, registers, serves, monitors, and triages a binary classification model on the UCI Bank Marketing dataset. The system detects drift in live prediction traffic, sends alerts to a LangGraph-based triage agent, pauses for human approval before Production-impacting actions, dispatches slow actions through a Redis queue, and exposes the full workflow through a Streamlit dashboard.

---

## Project Summary

The goal is to simulate a production-style MLOps system with an agentic response layer.

The system includes:

- A FastAPI model service for prediction serving, drift reporting, and registry promotion.
- A scikit-learn classification pipeline trained on the UCI Bank Marketing dataset.
- MLflow model registration with model artifacts, schema, and model card.
- Drift detection using PSI for numeric features, chi-square for categorical features, and output-distribution drift.
- A webhook contract between the model platform and the agent.
- A LangGraph supervisor with triage, action, and comms sub-agents.
- Postgres-backed investigation/checkpoint persistence.
- Redis-backed async queue with idempotency, retries, and DLQ.
- A worker service for long-running actions.
- A Streamlit dashboard for health, drift, investigations, queue status, and human approval.
- CI regression tests for model fidelity and agent trajectory snapshots.

---

## Architecture

```text
User / Dashboard
      ↓
Streamlit Dashboard
      ↓
FastAPI Model Service
      ├── /predict
      ├── /drift/report
      ├── /drift/check-and-notify
      └── /registry/promote

Model Service
      ↓ drift webhook
FastAPI Agent Service
      ↓
LangGraph Supervisor
      ├── Triage Agent
      ├── Action Agent
      └── Comms Agent
      ↓
Postgres Checkpoints + Investigations
      ↓ human approval
Redis Queue
      ↓
Worker
      ↓
Model Service Promotion Gate

More detail is available in:

## Documentation

- [Architecture](docs/ARCH.md)
- [Decisions](docs/DECISIONS.md)
- [Runbook](docs/RUNBOOK.md)
- [API Contract](docs/API_CONTRACT.md)


Dataset:

UCI Bank Marketing
bank-additional-full.csv


Binary classification: predict whether a customer subscribes to a term deposit.


Important dataset decisions:

duration is dropped because it leaks the target.
pdays == 999 is treated as a sentinel value.
unknown categorical values are preserved as meaningful categories.
The split is stratified 60/20/20 using random_state=42.


Model

The model is a scikit-learn pipeline:

raw data
→ preprocessing
→ classifier
→ calibrated operating threshold

The threshold is selected using the assignment rule:

Choose the highest validation threshold where recall >= 0.75.

Current metrics:

Operating threshold: 0.3845233329570477
Validation AUC: 0.801666278480117
Validation Recall: 0.75
Validation F1: 0.3699176189210736
Test AUC: 0.8012617045615359
Test Recall: 0.7478448275862069
Test F1: 0.3702320618831689

Artifacts saved/registerable:

artifacts/model_api/model.joblib
artifacts/model_api/threshold.json
artifacts/model_api/schema.json
artifacts/model_api/model_card.json
artifacts/model_api/reference_stats.json

Services
| Service     | Purpose                                                             |     Port |
| ----------- | ------------------------------------------------------------------- | -------: |
| `model_api` | Prediction, drift report, webhook sender, promotion gate            |   `8000` |
| `agent_api` | Drift webhook receiver, LangGraph workflow, approvals, queue status |   `8001` |
| `dashboard` | Streamlit operator dashboard                                        |   `8501` |
| `worker`    | Redis queue consumer for slow actions                               | internal |
| `postgres`  | Agent investigations and checkpoints                                |   `5432` |
| `redis`     | Action queue, retry queue, DLQ, idempotency keys                    |   `6379` |


Quick Start
1. Clone the repo
git clone https://github.com/aliasfahani/week-5-DRIFT-TRIAGE-CO-PILOT.git
cd week-5-DRIFT-TRIAGE-CO-PILOT
2. Create environment file
cp .env.example .env

On Windows PowerShell:
Copy-Item .env.example .env


3. Start the full stack
docker compose up --build

Open:

Model API: http://localhost:8000/docs
Agent API: http://localhost:8001/docs
Dashboard: http://localhost:8501


Local Development Without Docker

Create and activate a virtual environment:

python -m venv .venv

Windows PowerShell:

.venv\Scripts\Activate.ps1

Install dependencies:

pip install -e ".[dev]"

Train/refresh model artifacts:

python -m services.model_api.app.ml.train

Run model API:

python -m uvicorn services.model_api.app.main:app --reload --port 8000

Run agent API:

python -m uvicorn services.agent_api.app.main:app --reload --port 8001

Run dashboard:

streamlit run dashboard/app.py


### Core API Endpoints

| Endpoint                       | Purpose                                |
| ------------------------------ | -------------------------------------- |
| `GET /health`                  | Check model service health             |
| `POST /predict`                | Predict customer subscription          |
| `GET /drift/report`            | Generate drift report                  |
| `POST /drift/check-and-notify` | Send drift webhook if severity changed |
| `GET /registry/state`          | Show registry/Production state         |
| `POST /registry/promote`       | Promotion gate for Production changes  |


### Agent API

| Endpoint                       | Purpose                                 |
| ------------------------------ | --------------------------------------- |
| `GET /health`                  | Check agent service health              |
| `POST /webhooks/drift`         | Receive drift event from model platform |
| `GET /investigations`          | List investigations                     |
| `GET /approvals/pending`       | List HIL approvals                      |
| `POST /approvals/{id}/approve` | Approve Production-impacting action     |
| `POST /approvals/{id}/reject`  | Reject action                           |
| `GET /queue/status`            | Show queue, retry, and DLQ depth        |


###Drift Detection

The model API computes drift over a rolling window of recent predictions.

Drift checks:
| Drift type           | Method                         |
| -------------------- | ------------------------------ |
| Numeric features     | PSI                            |
| Categorical features | Chi-square                     |
| Model outputs        | Positive prediction-rate shift |

Agent Workflow

The agent uses a supervisor topology:

Supervisor
→ Triage Agent
→ Action Agent
→ Comms Agent

Responsibilities:

| Agent node | Role                                               |
| ---------- | -------------------------------------------------- |
| Supervisor | Starts/routs investigation                         |
| Triage     | Identifies numeric/categorical/output/mixed drift  |
| Action     | Recommends replay, retrain, rollback, or no action |
| Comms      | Creates dashboard-friendly operator summary        |

The trajectory is stored for regression testing.

Example trajectory:

supervisor → triage → action → comms

Prompts are stored under:

prompts/

This keeps prompts version-controlled and reviewable.


### Human-in-the-Loop Approval

Any action that can affect Production requires approval.

Examples:

retrain_candidate
rollback_candidate

Approval flow:

Agent recommends action
→ dashboard shows pending approval
→ human approves/rejects
→ approved actions are enqueued
→ worker executes action
→ promotion gate validates before Production change


### Redis Queue and Worker

Slow actions are dispatched through Redis instead of blocking the API.

Queue behavior:

Main queue for new jobs.
Retry queue for failed jobs with exponential backoff.
DLQ for exhausted jobs.
Idempotency keys prevent duplicate job execution.

Actions:

replay_test_set
retrain_candidate
rollback_candidate
Promotion Gate

Production changes go through:

POST /registry/promote

The gate checks:

model artifact exists
schema exists
model card exists
threshold exists
reference stats exist
tests/checklist passed
human approval exists
request came from the agent

This prevents direct unsafe Production promotion.

CI

The GitHub Actions workflow runs on push and pull request.

Expected checks:

dependency installation
docker compose config
pytest
agent trajectory snapshot regression test
model fidelity replay test

The model fidelity replay test guards against accidental prediction behavior changes by comparing predictor output with direct pipeline output at strict tolerance.
