# ARCH.md — Drift Triage Co-Pilot Architecture

## 1. Project Overview

Drift Triage Co-Pilot is a self-healing MLOps and agentic workflow system.

The project trains and serves a binary classifier on the UCI Bank Marketing dataset, monitors live prediction traffic for drift, sends drift alerts to an agent, lets the agent investigate the issue, pauses for human approval before Production-impacting actions, dispatches slow actions through Redis, and exposes the workflow through a Streamlit dashboard.

The system combines two required tracks:

1. **MLOps platform**
   - model training
   - artifact logging
   - MLflow/model registry
   - FastAPI prediction service
   - drift monitoring
   - promotion gate

2. **Agentic system**
   - LangGraph supervisor
   - triage/action/comms sub-agents
   - Postgres-backed checkpoints
   - Redis async queue
   - human-in-the-loop approval
   - dashboard visibility

---

## 2. High-Level Architecture

```text
                    ┌─────────────────────────┐
                    │   Streamlit Dashboard   │
                    │                         │
                    │ - Drift report          │
                    │ - Investigations        │
                    │ - HIL approvals         │
                    │ - Queue status          │
                    │ - Registry state        │
                    └───────────┬─────────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
     ┌─────────────────────┐          ┌─────────────────────┐
     │   Model API          │          │   Agent API          │
     │   FastAPI            │          │   FastAPI            │
     │                     │          │                     │
     │ /predict            │          │ /webhooks/drift     │
     │ /drift/report       │          │ /investigations     │
     │ /drift/check...     │          │ /approvals/pending  │
     │ /registry/promote   │          │ /queue/status       │
     └─────────┬───────────┘          └─────────┬───────────┘
               │                                │
               │ Drift webhook                  │ LangGraph checkpoints
               │                                │
               ▼                                ▼
     ┌─────────────────────┐          ┌─────────────────────┐
     │ Drift Event Contract │          │      Postgres        │
     │ contracts/*.json     │          │                     │
     └─────────────────────┘          │ agent_investigations│
                                      │ agent_checkpoints    │
                                      └─────────────────────┘

                         Human approval
                                │
                                ▼
                     ┌─────────────────────┐
                     │      Redis Queue     │
                     │                     │
                     │ queue:actions       │
                     │ queue:actions:retry │
                     │ queue:actions:dlq   │
                     └─────────┬───────────┘
                               │
                               ▼
                     ┌─────────────────────┐
                     │       Worker         │
                     │                     │
                     │ replay_test_set      │
                     │ retrain_candidate   │
                     │ rollback_candidate  │
                     └─────────┬───────────┘
                               │
                               │ Agent-approved platform call
                               ▼
                     ┌─────────────────────┐
                     │ Model API Registry   │
                     │ Promotion Gate       │
                     └─────────────────────┘

```text

## 3.Services

| Service                    | Technology                                      | Purpose                                                                                            |
| -------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `model_api`                | FastAPI + scikit-learn + MLflow/local artifacts | Serves predictions, computes drift, sends drift webhooks, exposes registry/promotion endpoints     |
| `agent_api`                | FastAPI + LangGraph                             | Receives drift webhooks, runs supervisor workflow, stores investigations, handles HIL approval     |
| `dashboard`                | Streamlit                                       | Operator UI for health, drift reports, investigations, approvals, queue status, and registry state |
| `worker`                   | Python service                                  | Consumes Redis jobs and executes slow actions such as replay, retrain, and rollback                |
| `postgres`                 | PostgreSQL                                      | Durable storage for agent investigations and LangGraph checkpoints                                 |
| `redis`                    | Redis                                           | Queue, retry queue, DLQ, and idempotency key storage                                               |
| `mlflow` / MLflow tracking | MLflow                                          | Model registry and artifact tracking, if enabled in final stack                                    |


## 4. Model Platform Architecture

The model platform is responsible for:

Training a binary classifier.
Saving/registering model artifacts.
Serving predictions over HTTP.
Logging recent predictions.
Computing drift reports.
Emitting drift webhooks.
Protecting Production changes through a promotion gate.
4.1 Training Pipeline

The training pipeline uses the UCI Bank Marketing dataset.

Important dataset decisions:

duration is dropped because it leaks the target.
pdays == 999 is treated as a sentinel value.
unknown categorical values are kept as real categories.
Target y is encoded as:
no → 0
yes → 1
Split strategy:
60% train
20% validation
20% test
stratified split
random_state=42

The model is a scikit-learn pipeline:

raw input
→ preprocessing
→ classifier
→ probability
→ operating threshold
→ binary prediction

4.2 Operating Threshold

The operating threshold is selected using the assignment rule:

Choose the highest validation threshold where recall >= 0.75.

Current recorded values:

Operating threshold: 0.3845233329570477
Validation AUC: 0.801666278480117
Validation Recall: 0.75
Validation F1: 0.3699176189210736
Test AUC: 0.8012617045615359
Test Recall: 0.7478448275862069
Test F1: 0.3702320618831689

The test recall is slightly below 0.75 because the threshold is tuned only on the validation set. The test set is used only for final evaluation.

4.3 Model Artifacts

The platform produces/registers these artifacts:

artifacts/model_api/model.joblib
artifacts/model_api/threshold.json
artifacts/model_api/schema.json
artifacts/model_api/model_card.json
artifacts/model_api/reference_stats.json

| Artifact               | Purpose                                                    |
| ---------------------- | ---------------------------------------------------------- |
| `model.joblib`         | Serialized fitted scikit-learn pipeline                    |
| `threshold.json`       | Saved operating threshold                                  |
| `schema.json`          | Expected input schema and feature decisions                |
| `model_card.json`      | Metrics, model metadata, hash, and environment fingerprint |
| `reference_stats.json` | Training/reference distributions for drift monitoring      |


## 5. Drift Monitoring Architecture

The model API computes drift over a rolling window of recent predictions.

5.1 Drift Types

| Drift type                | Method                         |
| ------------------------- | ------------------------------ |
| Numeric feature drift     | PSI                            |
| Categorical feature drift | Chi-square                     |
| Output distribution drift | Positive prediction-rate shift |

5.2 Drift Report Flow
POST /predict
    ↓
prediction is logged
    ↓
GET /drift/report
    ↓
compare recent prediction window against reference_stats.json
    ↓
return severity: low / medium / high

5.3 Drift Webhook Flow
POST /drift/check-and-notify
    ↓
generate drift report
    ↓
compare current severity with last severity
    ↓
if severity changed:
    build DriftEvent payload
    send POST /webhooks/drift to Agent API

Webhook is used instead of polling because drift events are naturally event-driven. The platform only contacts the agent when severity changes, avoiding unnecessary repeated agent runs.


## 6. Agent Architecture

The agent service receives drift events and opens investigations.

6.1 LangGraph Supervisor

The agent workflow follows a supervisor topology:

START
  ↓
supervisor
  ↓
triage
  ↓
action
  ↓
comms
  ↓
END

This is not just a simple API handler. The event is processed through structured nodes.

| Node         | Responsibility                                                                       |
| ------------ | ------------------------------------------------------------------------------------ |
| `supervisor` | Starts the investigation and sets routing/priority                                   |
| `triage`     | Classifies the type of drift: numeric, categorical, output, mixed, or none           |
| `action`     | Recommends action: no action, replay test set, retrain candidate, rollback candidate |
| `comms`      | Creates a dashboard-friendly summary for operators                                   |

6.2 Agent State

The graph state stores:

event_id
report_id
model_name
model_version
severity
previous_severity
drifted_features
drift_report
investigation_id
status
needs_human_approval
triage_summary
action_recommendation
comms_summary
trajectory

The trajectory is important because CI snapshot tests can detect unintended changes to agent routing.

Example trajectory:

supervisor → triage → action → comms
## 7. Postgres Persistence and Checkpoints

The agent persists state in Postgres.

Expected tables:

agent_investigations
agent_checkpoints
7.1 Why Postgres?

Postgres is used because:

investigations must survive service restarts;
checkpoints allow recovery from partial graph execution;
dashboard and API need durable state;
JSONL fallback is useful for local/dev mode but not enough for the full requirement.

7.2 Checkpoint Flow
drift event received
    ↓
save checkpoint at start
    ↓
run supervisor node
    ↓
save checkpoint
    ↓
run triage node
    ↓
save checkpoint
    ↓
run action node
    ↓
save checkpoint
    ↓
run comms node
    ↓
save final investigation

If the agent crashes mid-investigation, it can load the latest checkpoint and continue from the next node instead of restarting from zero.

## 8. Human-in-the-Loop Approval

The project requires human approval before any action touches Production.

Actions that require approval:

retrain_candidate
rollback_candidate

Approval flow:

Agent recommends Production-impacting action
    ↓
investigation status becomes pending_human_approval
    ↓
dashboard shows approval request
    ↓
operator approves or rejects
    ↓
approved actions are sent to Redis queue

Agent API endpoints:

GET /approvals/pending
POST /approvals/{investigation_id}/approve
POST /approvals/{investigation_id}/reject

## 9.Redis Queue and Worker Architecture
Slow actions are dispatched to Redis instead of running inside the API request.
9.1 Queues
queue:actions
queue:actions:retry
queue:actions:dlq

| Queue                 | Purpose                              |
| --------------------- | ------------------------------------ |
| `queue:actions`       | Main queue for approved jobs         |
| `queue:actions:retry` | Failed jobs waiting for retry        |
| `queue:actions:dlq`   | Dead-letter queue for exhausted jobs |

9.2 Idempotency

Idempotency keys prevent duplicate job execution.

Typical key:

investigation_id:action

This means if the same investigation/action is enqueued twice, Redis prevents duplicate processing.

9.3 Worker Flow
worker reads queue:actions
    ↓
executes job
    ↓
if success:
    mark complete
    ↓
if failure:
    increment attempt count
    ↓
if attempts remain:
    send to retry queue
    ↓
if attempts exhausted:
    send to DLQ
## 10. Promotion Gate Architecture

Production updates go through the model API promotion gate.

Endpoint:

POST /registry/promote

The gate validates:

model artifact exists;
schema exists;
model card exists;
threshold exists;
reference stats exist;
checklist passed;
human approval exists;
request came from the agent;
requested action is recorded.

This prevents direct unsafe Production mutation.

Expected flow:

human approves action
    ↓
agent enqueues Redis job
    ↓
worker consumes job
    ↓
worker calls model API /registry/promote
    ↓
promotion gate validates checklist
    ↓
registry state updates

## 11. Dashboard Architecture

The dashboard is the operator-facing UI.
Expected Pages: 

| Page                 | Purpose                                                   |
| -------------------- | --------------------------------------------------------- |
| Service Health       | Shows model and agent health                              |
| Drift Report         | Shows drift severity and lets user trigger notification   |
| Investigations       | Lists open/resolved investigations and graph trajectories |
| Human Approval Inbox | Approve/reject pending actions                            |
| Queue Status         | Shows main/retry/DLQ queue depths                         |
| Registry State       | Shows current Production registry state                   |

## 12. API Contract

The platform and agent communicate through a versioned contract.

Main integration:

Model API → Agent API
POST /webhooks/drift

Reverse integration:

Worker / Agent-approved action → Model API
POST /registry/promote

Contract rules:

payloads are versioned;
required fields are treated as breaking changes;
schema changes should update the contract version;
both services should validate payloads using Pydantic/JSON schema.

See:

docs/API_CONTRACT.md
contracts/drift_event.schema.json

##13. CI Architecture

CI should run on every push and pull request.

Expected checks:

dependency installation
docker compose config
pytest
agent trajectory snapshot tests
model fidelity replay test

Important tests:

| Test                           | Purpose                                                                         |
| ------------------------------ | ------------------------------------------------------------------------------- |
| Agent trajectory snapshot test | Ensures graph route/output does not silently change                             |
| Resume checkpoint test         | Ensures graph can continue from saved state                                     |
| Model fidelity replay test     | Ensures predictor output matches direct pipeline probability at 1e-12 tolerance |

##14. Failure and Recovery Design

| Failure                           | Handling                                        |
| --------------------------------- | ----------------------------------------------- |
| Agent crashes mid-investigation   | Resume from latest Postgres checkpoint          |
| Worker fails a job                | Retry with exponential backoff                  |
| Worker exhausts retries           | Move job to DLQ                                 |
| Duplicate approval/enqueue        | Redis idempotency key prevents duplicate action |
| Model promotion request is unsafe | Promotion gate rejects it                       |
| Dashboard refreshes               | Reads current API state from services           |
| Postgres unavailable in dev       | JSONL fallback can support local testing        |

## 15.Summary

The architecture implements a complete MLOps + agentic workflow:
train model
→ register artifacts
→ serve predictions
→ monitor drift
→ notify agent
→ investigate with LangGraph
→ pause for human approval
→ queue slow action
→ worker executes
→ promotion gate protects Production
→ dashboard shows the full process
