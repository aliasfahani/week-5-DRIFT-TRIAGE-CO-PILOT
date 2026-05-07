"""Redis queue helpers for slow operational actions."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from redis import Redis

MAIN_QUEUE = "queue:actions"
RETRY_QUEUE = "queue:actions:retry"
DLQ_QUEUE = "queue:actions:dlq"
IDEMPOTENCY_PREFIX = "queue:idempotency:"


def utc_now_iso() -> str:
    """Return current UTC timestamp as ISO8601."""
    return datetime.now(timezone.utc).isoformat()


def _redis_client() -> Redis:
    """Create Redis client from environment variables."""
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    return Redis(host=host, port=port, db=db, decode_responses=True)


def enqueue_action(
    *,
    investigation_id: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue action once using idempotency key and return enqueue metadata."""
    payload = payload or {}
    idempotency_key = f"{investigation_id}:{action}"
    idempotency_redis_key = f"{IDEMPOTENCY_PREFIX}{idempotency_key}"
    redis_client = _redis_client()

    inserted = redis_client.set(idempotency_redis_key, "1", nx=True, ex=24 * 60 * 60)
    if not inserted:
        return {
            "enqueued": False,
            "reason": "duplicate_idempotency_key",
            "idempotency_key": idempotency_key,
            "queue": MAIN_QUEUE,
        }

    job = {
        "job_id": f"job-{uuid.uuid4().hex[:12]}",
        "investigation_id": investigation_id,
        "action": action,
        "payload": payload,
        "idempotency_key": idempotency_key,
        "attempt": 0,
        "created_at": utc_now_iso(),
    }
    redis_client.lpush(MAIN_QUEUE, json.dumps(job))

    return {
        "enqueued": True,
        "queue": MAIN_QUEUE,
        "job": job,
    }


def queue_status() -> dict[str, int]:
    """Return queue depth for main, retry, and dead-letter queues."""
    redis_client = _redis_client()
    return {
        "main_depth": int(redis_client.llen(MAIN_QUEUE)),
        "retry_depth": int(redis_client.zcard(RETRY_QUEUE)),
        "dlq_depth": int(redis_client.llen(DLQ_QUEUE)),
    }
