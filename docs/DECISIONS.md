# DECISIONS

## 1) Rule-Based Graph Nodes Before LLM Calls

Decision:
- Keep supervisor/triage/action/comms as deterministic rule-based nodes first.

Why:
- Enables reproducible regression tests and trajectory snapshots in CI without API keys.
- Reduces moving parts while integrating queue/checkpoint infrastructure.

Trade-off:
- Less flexible than LLM-driven reasoning for nuanced triage.

## 2) Postgres + JSONL Fallback for Agent State

Decision:
- Use Postgres as the primary store for investigations/checkpoints, with JSONL fallback.

Why:
- Postgres is needed for durable, restart-safe state in a multi-service setup.
- Fallback keeps local development unblocked when DB wiring is absent.

Trade-off:
- Dual-path persistence adds maintenance complexity.

## 3) Redis Queues for Slow Action Execution

Decision:
- Dispatch slow actions through Redis-backed queues with idempotency, retry, and DLQ.

Why:
- Prevents API request handlers from blocking on long-running tasks.
- Gives clear operational behavior for failure handling and replay safety.

Trade-off:
- Adds worker and queue observability overhead.

## 4) Promotion Through Programmatic Gate Only

Decision:
- Route production-impacting actions through `model_api /registry/promote`.

Why:
- Centralizes promotion checks and enforces a consistent approval checklist.
- Aligns with assignment requirement that production changes happen through a controlled gate.

Trade-off:
- Promotion behavior is currently local-registry based and can require further hardening with MLflow stage controls.

## 5) Single Compose Stack for Demo and Onboarding

Decision:
- Standardize startup around `docker compose up`.

Why:
- Improves reproducibility for partner review and presentation setup.
- Reduces "works on my machine" drift between services.

Trade-off:
- Requires container/runtime setup even for quick component-only testing.
