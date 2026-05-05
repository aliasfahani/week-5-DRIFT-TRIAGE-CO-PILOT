"""Train the first project model pipeline.

This script will eventually:
- load bank-additional-full.csv,
- split train/validation/test with stratification,
- train a preprocessing + classifier pipeline,
- tune the highest threshold with recall >= 0.75,
- report validation and test metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.model_selection import train_test_split

from services.model_api.app.ml.evaluate import classification_metrics_at_threshold
from services.model_api.app.ml.preprocess import (
    RANDOM_STATE,
    build_preprocessing_classifier_pipeline,
    load_bank_marketing_csv,
    prepare_features_and_target,
)
from services.model_api.app.ml.threshold import select_highest_threshold_for_recall

DEFAULT_DATA_PATH = Path("data/raw/bank-additional-full.csv")
ASSIGNMENT_DATA_PATH = Path("bank+marketing/bank-additional/bank-additional-full.csv")


def resolve_data_path() -> Path:
    """Find the training CSV in the standard project path or assignment download."""
    if DEFAULT_DATA_PATH.exists():
        return DEFAULT_DATA_PATH
    if ASSIGNMENT_DATA_PATH.exists():
        return ASSIGNMENT_DATA_PATH
    raise FileNotFoundError(
        "Could not find bank-additional-full.csv. Place it at "
        f"{DEFAULT_DATA_PATH} or keep the assignment download at {ASSIGNMENT_DATA_PATH}."
    )


def train_model(data_path: Path | None = None):
    """Train the pipeline and return the fitted model, threshold, and metrics."""
    data = load_bank_marketing_csv(data_path or resolve_data_path())
    X, y = prepare_features_and_target(data)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X,
        y,
        test_size=0.4,
        stratify=y,
        random_state=RANDOM_STATE,
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp,
        y_temp,
        test_size=0.5,
        stratify=y_temp,
        random_state=RANDOM_STATE,
    )

    pipeline = build_preprocessing_classifier_pipeline()
    pipeline.fit(X_train, y_train)

    val_scores = pipeline.predict_proba(X_val)[:, 1]
    threshold_result = select_highest_threshold_for_recall(
        y_val,
        val_scores,
        min_recall=0.75,
    )
    threshold = threshold_result["threshold"]

    test_scores = pipeline.predict_proba(X_test)[:, 1]
    return {
        "pipeline": pipeline,
        "threshold": threshold,
        "validation": classification_metrics_at_threshold(y_val, val_scores, threshold),
        "test": classification_metrics_at_threshold(y_test, test_scores, threshold),
        "split_sizes": {
            "train": len(X_train),
            "validation": len(X_val),
            "test": len(X_test),
        },
    }


def main() -> None:
    """Run the training workflow."""
    result = train_model()
    printable = {
        "selected_threshold": result["threshold"],
        "split_sizes": result["split_sizes"],
        "validation": result["validation"],
        "test": result["test"],
    }
    print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    main()
