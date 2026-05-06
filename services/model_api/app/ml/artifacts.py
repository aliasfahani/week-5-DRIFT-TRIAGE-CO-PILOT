"""Model artifact saving/loading utilities."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import joblib
import sklearn

from services.model_api.app.ml.preprocess import (
    CATEGORICAL_COLUMNS,
    LEAKAGE_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMN,
)

ARTIFACT_DIR = Path("artifacts/model_api")

MODEL_PATH = ARTIFACT_DIR / "model.joblib"
THRESHOLD_PATH = ARTIFACT_DIR / "threshold.json"
SCHEMA_PATH = ARTIFACT_DIR / "schema.json"
MODEL_CARD_PATH = ARTIFACT_DIR / "model_card.json"
REFERENCE_STATS_PATH = ARTIFACT_DIR / "reference_stats.json"


def ensure_artifact_dir() -> None:
    """Create the artifact directory if it does not exist."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Save a dictionary as pretty JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    """Compute SHA256 hash for an artifact file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_schema() -> dict[str, Any]:
    """Build the model input schema metadata."""
    return {
        "target_column": TARGET_COLUMN,
        "dropped_columns": list(LEAKAGE_COLUMNS),
        "numeric_columns": list(NUMERIC_COLUMNS),
        "categorical_columns": list(CATEGORICAL_COLUMNS),
        "required_raw_input_columns": [
            "age",
            "job",
            "marital",
            "education",
            "default",
            "housing",
            "loan",
            "contact",
            "month",
            "day_of_week",
            "campaign",
            "pdays",
            "previous",
            "poutcome",
            "emp.var.rate",
            "cons.price.idx",
            "cons.conf.idx",
            "euribor3m",
            "nr.employed",
        ],
        "engineered_columns": ["pdays_was_999"],
        "notes": [
            "duration is intentionally dropped because it leaks the target.",
            "pdays == 999 is converted to pdays = -1 and pdays_was_999 = 1.",
            "unknown categorical values are preserved as valid categories.",
        ],
    }


def build_model_card(
    *,
    threshold: float,
    validation_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    split_sizes: dict[str, int],
    model_hash: str,
) -> dict[str, Any]:
    """Build a simple model card for the trained classifier."""
    return {
        "model_name": "bank_marketing_classifier",
        "model_type": "sklearn_pipeline_logistic_regression",
        "dataset": "UCI Bank Marketing bank-additional-full.csv",
        "target": TARGET_COLUMN,
        "operating_threshold": threshold,
        "threshold_rule": "highest validation threshold with recall >= 0.75",
        "split_strategy": "stratified 60/20/20 split with random_state=42",
        "split_sizes": split_sizes,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "model_sha256": model_hash,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "scikit_learn": sklearn.__version__,
        },
        "important_data_decisions": [
            "Dropped duration to prevent target leakage.",
            "Encoded target y as no=0 and yes=1.",
            "Handled pdays == 999 as a sentinel value.",
            "Kept unknown as a meaningful category.",
        ],
    }


def save_training_artifacts(
    *,
    pipeline,
    threshold: float,
    validation_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    split_sizes: dict[str, int],
    reference_stats: dict[str, Any],
) -> dict[str, str]:
    """Save the trained model and metadata artifacts."""
    ensure_artifact_dir()

    joblib.dump(pipeline, MODEL_PATH)

    threshold_payload = {
        "threshold": threshold,
        "rule": "highest validation threshold with recall >= 0.75",
    }
    save_json(THRESHOLD_PATH, threshold_payload)

    schema = build_schema()
    save_json(SCHEMA_PATH, schema)

    save_json(REFERENCE_STATS_PATH, reference_stats)

    model_hash = file_sha256(MODEL_PATH)
    model_card = build_model_card(
        threshold=threshold,
        validation_metrics=validation_metrics,
        test_metrics=test_metrics,
        split_sizes=split_sizes,
        model_hash=model_hash,
    )
    save_json(MODEL_CARD_PATH, model_card)

    return {
        "model_path": str(MODEL_PATH),
        "threshold_path": str(THRESHOLD_PATH),
        "schema_path": str(SCHEMA_PATH),
        "model_card_path": str(MODEL_CARD_PATH),
        "reference_stats_path": str(REFERENCE_STATS_PATH),
    }


def load_model():
    """Load the fitted sklearn pipeline."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model artifact not found at {MODEL_PATH}. "
            "Run: python -m services.model_api.app.ml.train"
        )
    return joblib.load(MODEL_PATH)


def load_threshold() -> float:
    """Load the operating threshold."""
    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError(
            f"Threshold artifact not found at {THRESHOLD_PATH}. "
            "Run training first."
        )
    return float(load_json(THRESHOLD_PATH)["threshold"])