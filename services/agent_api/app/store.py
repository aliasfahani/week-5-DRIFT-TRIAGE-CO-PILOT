"""Investigation store with Postgres-backed checkpoints.

Primary storage is Postgres when connection settings are available.
Fallback storage remains JSONL for local/dev environments.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime")
INVESTIGATION_LOG_PATH = RUNTIME_DIR / "agent_investigations.jsonl"
CHECKPOINT_LOG_PATH = RUNTIME_DIR / "agent_checkpoints.jsonl"
_SCHEMA_READY = False


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _postgres_dsn() -> str | None:
    """Build Postgres DSN from environment variables."""
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DB")

    if not all((host, user, password, database)):
        return None

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _get_postgres_connection():
    """Create a Postgres connection, or return None when unavailable."""
    dsn = _postgres_dsn()
    if dsn is None:
        return None

    try:
        import psycopg
    except ModuleNotFoundError:
        return None

    try:
        return psycopg.connect(dsn)
    except Exception:
        return None


def _ensure_postgres_schema() -> bool:
    """Create required Postgres tables once per process."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return True

    connection = _get_postgres_connection()
    if connection is None:
        return False

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_investigations (
                        id BIGSERIAL PRIMARY KEY,
                        investigation_id TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agent_investigations_id_created
                    ON agent_investigations (investigation_id, created_at DESC)
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_checkpoints (
                        id BIGSERIAL PRIMARY KEY,
                        investigation_id TEXT NOT NULL,
                        node_name TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agent_checkpoints_id_created
                    ON agent_checkpoints (investigation_id, created_at DESC)
                    """
                )
        _SCHEMA_READY = True
        return True
    finally:
        connection.close()


def save_investigation(investigation: dict[str, Any]) -> None:
    """Persist investigation state to Postgres or JSONL fallback."""
    if _ensure_postgres_schema():
        connection = _get_postgres_connection()
        if connection is not None:
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO agent_investigations (investigation_id, payload)
                            VALUES (%s, %s::jsonb)
                            """,
                            (
                                investigation["investigation_id"],
                                json.dumps(investigation),
                            ),
                        )
                return
            finally:
                connection.close()

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    with INVESTIGATION_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(investigation) + "\n")


def save_checkpoint(
    *,
    investigation_id: str,
    node_name: str,
    state: dict[str, Any],
) -> None:
    """Persist one workflow checkpoint to Postgres or JSONL fallback."""
    checkpoint = {
        "investigation_id": investigation_id,
        "node_name": node_name,
        "state": state,
        "created_at": utc_now_iso(),
    }

    if _ensure_postgres_schema():
        connection = _get_postgres_connection()
        if connection is not None:
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO agent_checkpoints (investigation_id, node_name, payload)
                            VALUES (%s, %s, %s::jsonb)
                            """,
                            (
                                investigation_id,
                                node_name,
                                json.dumps(checkpoint),
                            ),
                        )
                return
            finally:
                connection.close()

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(checkpoint) + "\n")


def get_latest_checkpoint(investigation_id: str) -> dict[str, Any] | None:
    """Load the newest checkpoint for one investigation."""
    if _ensure_postgres_schema():
        connection = _get_postgres_connection()
        if connection is not None:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT payload::text
                        FROM agent_checkpoints
                        WHERE investigation_id = %s
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """,
                        (investigation_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        return None
                    return json.loads(row[0])
            finally:
                connection.close()

    if not CHECKPOINT_LOG_PATH.exists():
        return None

    latest: dict[str, Any] | None = None
    with CHECKPOINT_LOG_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("investigation_id") == investigation_id:
                latest = entry
    return latest


def _read_all_versions() -> list[dict[str, Any]]:
    """Read all investigation versions from Postgres or JSONL fallback."""
    if _ensure_postgres_schema():
        connection = _get_postgres_connection()
        if connection is not None:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT payload::text
                        FROM agent_investigations
                        ORDER BY created_at ASC, id ASC
                        """
                    )
                    return [json.loads(row[0]) for row in cursor.fetchall()]
            finally:
                connection.close()

    if not INVESTIGATION_LOG_PATH.exists():
        return []

    investigations: list[dict[str, Any]] = []

    with INVESTIGATION_LOG_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                investigations.append(json.loads(line))

    return investigations


def list_investigations() -> list[dict[str, Any]]:
    """Return the latest state per investigation."""
    latest_by_id: dict[str, dict[str, Any]] = {}

    for investigation in _read_all_versions():
        investigation_id = investigation["investigation_id"]
        latest_by_id[investigation_id] = investigation

    return list(latest_by_id.values())


def get_investigation(investigation_id: str) -> dict[str, Any] | None:
    """Get the latest version of one investigation."""
    for investigation in list_investigations():
        if investigation["investigation_id"] == investigation_id:
            return investigation

    return None


def list_pending_approvals() -> list[dict[str, Any]]:
    """List investigations waiting for human approval."""
    return [
        investigation
        for investigation in list_investigations()
        if investigation.get("status") == "pending_human_approval"
    ]


def approve_investigation(
    *,
    investigation_id: str,
    approved_by: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    """Approve a pending investigation."""
    investigation = get_investigation(investigation_id)

    if investigation is None:
        return None

    updated = {
        **investigation,
        "status": "approved",
        "approved_by": approved_by,
        "approval_note": note,
        "approved_at": utc_now_iso(),
    }

    save_investigation(updated)
    return updated


def reject_investigation(
    *,
    investigation_id: str,
    rejected_by: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    """Reject a pending investigation."""
    investigation = get_investigation(investigation_id)

    if investigation is None:
        return None

    updated = {
        **investigation,
        "status": "rejected",
        "rejected_by": rejected_by,
        "rejection_note": note,
        "rejected_at": utc_now_iso(),
    }

    save_investigation(updated)
    return updated