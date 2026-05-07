# RUNBOOK

## 1) Local Startup

1. Copy environment template:
   - `cp .env.example .env`
2. Start stack:
   - `docker compose up --build`
3. Open services:
   - Model API: `http://localhost:8000/docs`
   - Agent API: `http://localhost:8001/docs`
   - Dashboard: `http://localhost:8501`

## 2) Train/Refresh Model Artifacts

If artifacts are missing or stale, run training:

- `python -m services.model_api.app.ml.train`

Expected outputs under `artifacts/model_api/`:
- `model.joblib`
- `threshold.json`
- `schema.json`
- `model_card.json`
- `reference_stats.json`

## 3) Drift + Investigation Flow

1. Send predictions to `POST /predict` (Model API).
2. Trigger `POST /drift/check-and-notify`.
3. Check investigations in dashboard "Investigations" page.
4. If pending approvals exist, review under "Human Approval Inbox".

## 4) Queue Operations

- Check queue depth via:
  - Agent endpoint: `GET /queue/status`
  - Dashboard page: "Queue Status"
- Worker handles:
  - retries with exponential backoff,
  - DLQ routing after max attempts.

## 5) Promotion Gate

Production-impacting actions are routed by worker to:
- `POST /registry/promote` (Model API)

Registry state can be checked at:
- `GET /registry/state`

## 6) CI

CI workflow file:
- `.github/workflows/ci.yml`

Current checks include:
- dependency install,
- `docker compose config`,
- `pytest -q` regression suite.

## 7) Common Failures

- **Missing model artifacts**:
  - Re-run training command.
- **Postgres unavailable**:
  - Check `docker compose ps` and service health.
- **Redis queue not draining**:
  - Confirm worker container is running.
- **Promotion gate fails**:
  - Inspect checklist/human approval fields in queued action payload.
