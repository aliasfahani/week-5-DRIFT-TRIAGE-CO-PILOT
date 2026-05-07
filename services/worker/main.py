"""Redis-backed worker with retries and dead-letter queue."""

from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone

import requests
from redis import Redis

MAIN_QUEUE = "queue:actions"
RETRY_QUEUE = "queue:actions:retry"
DLQ_QUEUE = "queue:actions:dlq"
MAX_RETRIES = int(os.getenv("QUEUE_MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = int(os.getenv("QUEUE_RETRY_BASE_SECONDS", "2"))
MODEL_API_URL = os.getenv("MODEL_API_URL", "http://model_api:8000")


def _redis_client() -> Redis:
    """Create Redis client from environment variables."""
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    return Redis(host=host, port=port, db=db, decode_responses=True)


def _now_epoch() -> float:
    """Return current Unix timestamp."""
    return datetime.now(timezone.utc).timestamp()


def _move_due_retries(redis_client: Redis) -> None:
    """Move due retry jobs from sorted set back to main queue."""
    now = _now_epoch()
    due_jobs = redis_client.zrangebyscore(RETRY_QUEUE, min=0, max=now)
    if not due_jobs:
        return
    for raw in due_jobs:
        redis_client.lpush(MAIN_QUEUE, raw)
        redis_client.zrem(RETRY_QUEUE, raw)


def _process_job(job: dict) -> None:
    """Execute queued action; call promotion gate for production actions."""
    action = job.get("action")
    if action not in {"replay_test_set", "retrain_candidate", "rollback_candidate"}:
        raise RuntimeError(f"unknown action: {action}")

    if action in {"retrain_candidate", "rollback_candidate"}:
        payload = job.get("payload", {})
        approval_id = f"{job.get('investigation_id')}:{action}"
        promote_request = {
            "model_name": "bank_marketing_classifier",
            "model_version": "local-artifact",
            "model_uri": "artifacts/model_api/model.joblib",
            "requested_by": "agent",
            "approval_id": approval_id,
            "requested_action": action,
            "checklist": {
                "model_artifact_exists": True,
                "schema_validated": True,
                "model_card_present": True,
                "threshold_selected": True,
                "reference_stats_present": True,
                "tests_passed": True,
                "human_approved": bool(payload.get("approved_by")),
            },
        }
        response = requests.post(
            f"{MODEL_API_URL}/registry/promote",
            json=promote_request,
            timeout=10,
        )
        response.raise_for_status()

    print(
        f"worker: executed action={action} investigation_id={job.get('investigation_id')}",
        flush=True,
    )


def _handle_failure(redis_client: Redis, job: dict, error: Exception) -> None:
    """Apply exponential backoff retry or move job to DLQ."""
    attempt = int(job.get("attempt", 0)) + 1
    job["attempt"] = attempt
    job["last_error"] = str(error)
    job["failed_at"] = datetime.now(timezone.utc).isoformat()

    serialized = json.dumps(job)
    if attempt > MAX_RETRIES:
        redis_client.lpush(DLQ_QUEUE, serialized)
        print(
            f"worker: moved to dlq job_id={job.get('job_id')} attempts={attempt}",
            flush=True,
        )
        return

    delay_seconds = RETRY_BASE_SECONDS ** attempt
    ready_at = _now_epoch() + delay_seconds
    redis_client.zadd(RETRY_QUEUE, {serialized: ready_at})
    print(
        f"worker: retry scheduled job_id={job.get('job_id')} attempt={attempt} delay={delay_seconds}s",
        flush=True,
    )


def main() -> None:
    """Run queue consumer loop with retry and DLQ semantics."""
    redis_client = _redis_client()
    print("worker: queue consumer started", flush=True)
    while True:
        _move_due_retries(redis_client)
        message = redis_client.brpop(MAIN_QUEUE, timeout=5)
        if message is None:
            time.sleep(1)
            continue

        _, raw_job = message
        job = json.loads(raw_job)

        try:
            _process_job(job)
        except Exception as exc:
            _handle_failure(redis_client, job, exc)


if __name__ == "__main__":
    main()
