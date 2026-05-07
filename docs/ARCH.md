# ARCH

## System Overview

The stack is composed of:

- `model_api` (FastAPI): serves predictions, computes drift reports, and exposes promotion-gate endpoints.
- `agent_api` (FastAPI + LangGraph): consumes drift events, runs supervisor/triage/action/comms flow, and manages HIL approvals.
- `worker` (Python process): consumes async action jobs from Redis, retries failed jobs with backoff, and sends production-impacting actions to the model promotion gate.
- `dashboard` (Streamlit): operator UI for health, investigations, approvals, and queue depth.
- `postgres`: durable store for investigations and checkpoints.
- `redis`: async queue, retry queue, idempotency keys, and DLQ backend.

## Key Data Flows

1. Prediction request arrives at `model_api`.
2. Prediction is logged and drift report can be generated.
3. On severity change, `model_api` emits webhook to `agent_api`.
4. `agent_api` runs LangGraph workflow and stores checkpoints/investigation state.
5. If action requires human approval, it appears in dashboard inbox.
6. Approved actions are enqueued in Redis.
7. `worker` consumes actions and executes:
   - non-production actions directly (replay path scaffolded),
   - production-impacting actions through `model_api /registry/promote`.
8. Dashboard reflects investigation status and queue depth.

## Persistence Strategy

- Postgres is the primary persistence backend for agent investigations and checkpoints.
- JSONL fallback remains available for local/dev resilience when Postgres settings are missing.
- Redis stores:
  - main action queue,
  - retry queue (sorted set with schedule times),
  - dead-letter queue,
  - idempotency keys.

## Runtime Topology

Local development and demo startup are orchestrated through `docker-compose.yml` using a shared app image (`Dockerfile`) and service-to-service DNS names (`model_api`, `agent_api`, `redis`, `postgres`).
