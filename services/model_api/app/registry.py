"""Local registry-state and promotion-gate helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.model_api.app.ml.artifacts import (
    MODEL_CARD_PATH,
    MODEL_PATH,
    REFERENCE_STATS_PATH,
    SCHEMA_PATH,
    THRESHOLD_PATH,
    load_json,
)
from services.model_api.app.schemas import PromotionRequest

RUNTIME_DIR = Path("runtime")
REGISTRY_STATE_PATH = RUNTIME_DIR / "registry_state.json"


def load_registry_state(path: Path = REGISTRY_STATE_PATH) -> dict[str, Any]:
    """Load registry state from durable local storage."""
    if not path.exists():
        return {"production": None, "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry_state(state: dict[str, Any], path: Path = REGISTRY_STATE_PATH) -> None:
    """Persist registry state to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def artifact_status() -> dict[str, bool]:
    """Return whether required artifacts are available."""
    return {
        "model": MODEL_PATH.exists(),
        "schema": SCHEMA_PATH.exists(),
        "model_card": MODEL_CARD_PATH.exists(),
        "threshold": THRESHOLD_PATH.exists(),
        "reference_stats": REFERENCE_STATS_PATH.exists(),
    }


def assert_promotion_gate(request: PromotionRequest) -> None:
    """Validate gate conditions before Production promotion."""
    missing_artifacts = [name for name, exists in artifact_status().items() if not exists]
    if missing_artifacts:
        raise ValueError(f"Cannot promote with missing artifacts: {', '.join(missing_artifacts)}")

    failed_checks = [name for name, value in request.checklist.model_dump().items() if value is not True]
    if failed_checks:
        raise ValueError(f"Promotion checklist failed: {', '.join(failed_checks)}")

    if not request.approval_id:
        raise ValueError("Promotion requires a human approval id.")

    if request.requested_by != "agent":
        raise ValueError("Production promotion must be requested by the agent.")


def promote_to_production(request: PromotionRequest) -> dict[str, Any]:
    """Promote model to Production after gate validation."""
    assert_promotion_gate(request)
    model_card = load_json(MODEL_CARD_PATH)
    state = load_registry_state()

    production_record = {
        "model_name": request.model_name,
        "model_version": request.model_version,
        "model_uri": request.model_uri,
        "stage": "Production",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": request.requested_by,
        "approval_id": request.approval_id,
        "requested_action": request.requested_action,
        "model_card": {
            "operating_threshold": model_card.get("operating_threshold"),
            "validation_metrics": model_card.get("validation_metrics"),
            "test_metrics": model_card.get("test_metrics"),
            "model_sha256": model_card.get("model_sha256"),
        },
    }

    state["production"] = production_record
    state.setdefault("history", []).append(production_record)
    save_registry_state(state)
    return production_record
