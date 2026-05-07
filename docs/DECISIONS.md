```text
# DECISIONS.md — Project Design Decisions

This document explains the major technical and design decisions made in Drift Triage Co-Pilot.

---

## 1. Webhook Instead of Polling

### Decision

The model platform sends a webhook to the agent when drift severity changes.

### Why

Drift events are event-driven. The agent does not need to constantly poll the platform for changes.

Webhook benefits:

- lower overhead;
- faster reaction to severity changes;
- cleaner integration contract;
- easier to demo;
- avoids repeated agent investigations for unchanged severity.

### Tradeoff

If the agent is down when the webhook is sent, the event may fail unless retry behavior is added. In the current system, this is handled at a basic integration level and can be improved with retry/outbox patterns later.

---

## 2. Versioned API Contract

### Decision

The model platform and agent communicate using a documented, versioned contract.

Main contract:

```text
POST /webhooks/drift

Contract version:

v1
Why

The platform and agent are separate services. A schema change in one service can break the other service.

Versioning makes integration safer.

Rule

Any change to required fields, field names, severity values, or action values should be treated as a breaking change and should produce a new contract version.

3. Dropping duration
Decision

The duration column is dropped before training.

Why

In the UCI Bank Marketing dataset, duration is recorded after the phone call ends. That means it is not available before prediction time and leaks information about the target.

Keeping it would make the model look unrealistically good.

Result

The model is trained only on features that are valid before the outcome is known.

4. Treating pdays == 999 as a Sentinel
Decision

pdays == 999 is treated as a sentinel value, not a normal numeric value.

The system creates a flag:

pdays_was_999

and replaces pdays == 999 with a safer encoded value.

Why

In the dataset, 999 means the customer was not previously contacted. It is not a normal number of days.

Result

The model can learn both:

whether the customer was never contacted;
the real number of days for customers who were contacted.
5. Keeping unknown as a Category
Decision

unknown categorical values are preserved as real categories.

Why

The assignment states that unknown is informative and should not be treated as missing data.

For example, an unknown job, default status, or education value may correlate with the target.

Result

The categorical encoder treats unknown like any other category.

6. Stratified 60/20/20 Split
Decision

The dataset is split into:

60% train
20% validation
20% test

with stratification and random_state=42.

Why

The target is imbalanced. Only around 11% of customers subscribe to the term deposit.

Stratification keeps the class distribution stable across train, validation, and test splits.

Result

The validation and test metrics are more reliable.

7. Threshold Rule: Recall >= 0.75
Decision

The operating threshold is selected as the highest validation threshold that keeps recall at or above 0.75.

Why

The assignment explicitly requires this threshold rule.

A lower threshold catches more positives but may create more false positives. The chosen rule balances recall with a stricter threshold.

Current Threshold
0.3845233329570477
Result

The model is not using the default 0.5 threshold. It uses the saved operating threshold from validation tuning.

8. Saving a Model Artifact Triple
Decision

The model pipeline is saved with supporting artifacts:

model.joblib
schema.json
model_card.json
threshold.json
reference_stats.json
Why

A production system needs more than a model binary.

It needs:

the model itself;
expected input schema;
operating threshold;
model card with metrics and environment details;
reference stats for drift monitoring.
Result

The model can be served, audited, monitored, and registered.

9. MLflow / Registry Tracking
Decision

Model registration is handled through MLflow and/or a local registry gate depending on the runtime setup.

Why

The assignment requires MLflow registration with the artifact triple. The registry also needs to support safe Production promotion.

MLflow is useful for:

model versioning;
artifact tracking;
metric logging;
reproducible model lineage.

The local promotion gate is useful for:

enforcing approval/checklist rules;
storing current Production state;
rejecting unsafe promotions.
Result

The system separates model tracking from Production promotion safety.

10. Drift Methods
Decision

The system uses:

Drift type Method
Numeric drift PSI
Categorical drift Chi-square
Output drift Positive prediction-rate difference
Why

The assignment requires:

PSI on numerics
chi-square on categoricals
output-distribution drift
Result

The drift report can detect changes in:

numeric input distributions;
categorical input distributions;
model output behavior.
11. LangGraph Supervisor Topology
Decision

The agent uses a supervisor-style graph with three sub-agents:

supervisor → triage → action → comms
Why

The assignment requires a true supervisor topology with triage, action, and comms sub-agents, not just a simple chain.

Node Responsibilities
Node Purpose
Supervisor Starts/routes the investigation
Triage Diagnoses drift type and severity
Action Recommends replay/retrain/rollback/no action
Comms Produces human-readable dashboard summary
Result

Each drift event becomes a structured investigation with a visible trajectory.

12. Rule-Based / Mocked Agent Logic
Decision

The first implementation uses deterministic rule-based logic rather than a live LLM call.

Why

The assignment requires CI tests to mock the LLM so tests run without an API key.

Deterministic rules make the graph:

testable;
reproducible;
easier to explain;
stable for snapshot regression tests.
Result

The graph can later be connected to an LLM provider while preserving the same nodes and state shape.

13. Prompts Stored as Files
Decision

Prompts are stored in:

prompts/

instead of inline Python strings.

Why

The assignment says prompts must be treated as code.

This makes prompt changes:

visible in Git;
reviewable in Pull Requests;
version-controlled;
easier to test.
14. Postgres for Agent Persistence
Decision

Agent investigations and checkpoints are stored in Postgres.

Why

The agent must survive restarts and resume investigations from the latest checkpoint.

Postgres provides durable storage for:

investigation records;
intermediate graph states;
checkpoint recovery;
dashboard queries.
Result

If the agent crashes mid-investigation, it can load the latest checkpoint and continue.

15. JSONL Fallback for Local Development
Decision

A JSONL fallback is available when Postgres environment variables are not configured.

Why

This makes local development easier.

A developer can test the app without running Postgres.

Tradeoff

JSONL fallback is not the final production persistence layer. Postgres is the expected durable path for the full stack.

16. Redis Queue for Slow Actions
Decision

Slow actions are dispatched through Redis.

Actions include:

replay_test_set
retrain_candidate
rollback_candidate
Why

Slow actions should not block the agent API request.

Redis provides:

queueing;
idempotency key storage;
retry queue;
dead-letter queue;
operational queue depth metrics.
Result

The API stays responsive while the worker handles long-running tasks asynchronously.

17. Idempotency Keys
Decision

Queue jobs use idempotency keys such as:

investigation_id:action
Why

Retries, duplicate approvals, or repeated API calls should not create duplicate retrain/rollback jobs.

Result

Redis SET NX behavior prevents duplicate enqueueing for the same investigation/action pair.

18. Retry Queue and Dead-Letter Queue
Decision

Failed jobs are retried with exponential backoff. Exhausted jobs move to a DLQ.

Why

Some failures are temporary, such as service availability or network issues.

Retries allow recovery.

The DLQ preserves failed jobs for inspection instead of silently dropping them.

Result

The queue is safer and more observable.

19. Human Approval Before Production Changes
Decision

Actions that touch Production require human approval.

Examples:

retrain_candidate
rollback_candidate
Why

The assignment requires HIL approval before any Production change reaches the registry.

This also protects against stale or unsafe agent recommendations.

Result

The agent can recommend actions, but it cannot directly mutate Production without approval.

20. Programmatic Promotion Gate
Decision

Production updates go through:

POST /registry/promote
Why

The platform should refuse unsafe promotions.

The gate checks:

artifacts;
model card;
schema;
threshold;
reference stats;
checklist;
human approval;
agent origin.
Result

Even if a worker calls the platform, the platform still validates the promotion request before updating registry state.

21. Streamlit Dashboard
Decision

The dashboard is built in Streamlit.

Why

Streamlit is fast to build and good for operational dashboards.

It allows the project to show:

health checks;
drift reports;
investigations;
approval inbox;
queue status;
registry state.
Result

The Friday demo can be shown visually instead of only through API docs.

22. Docker Compose
Decision

The full system is orchestrated with Docker Compose.

Why

The assignment requires the repo to come up from a clean clone using Docker Compose.

Compose provides:

model API container;
agent API container;
dashboard container;
worker container;
Redis container;
Postgres container;
shared service network;
persistent volumes.
Result

The project can be started as one integrated stack instead of manually running each piece.

23. CI Regression Tests
Decision

CI runs on push and pull request.

Expected checks:

pytest
docker compose config
agent trajectory snapshot tests
model fidelity replay test
Why

The assignment requires agent decision logic and full trajectories to be under regression test.

The model fidelity test catches accidental changes in the prediction path.

Result

The project is protected against silent regressions.

24. Known Tradeoffs

The current system is a strong integration-level implementation, but some parts are simplified:

Some agent logic is deterministic rather than real LLM-based.
Some slow actions may be scaffolds instead of full retraining pipelines.
Local runtime files may be used as fallback.
MLflow/local registry behavior depends on the final committed setup.
The demo requires seeded prediction traffic to produce meaningful drift.

These tradeoffs are acceptable if clearly explained during the demo and documented in the README.

25. Summary

The design prioritizes:

safe Production changes
visible drift response
durable agent state
asynchronous slow actions
deterministic agent tests
clean Docker startup
clear demo flow

The final system demonstrates how an MLOps platform and an agentic supervisor can work together to monitor, investigate, and safely respond to model drift.
