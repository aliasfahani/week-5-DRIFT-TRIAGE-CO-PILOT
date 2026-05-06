"""Reference statistics used for drift detection."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from services.model_api.app.ml.preprocess import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS


def _numeric_reference(series: pd.Series, bins: int = 10) -> dict[str, Any]:
    """Create reference histogram statistics for a numeric column."""
    clean = pd.to_numeric(series, errors="coerce").dropna()

    if clean.empty:
        return {
            "bin_edges": [0.0, 1.0],
            "proportions": [1.0],
        }

    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(clean, quantiles))

    if len(edges) < 2:
        value = float(clean.iloc[0])
        edges = np.array([value - 0.5, value + 0.5])

    counts, bin_edges = np.histogram(clean, bins=edges)
    total = counts.sum()

    if total == 0:
        proportions = np.ones(len(counts)) / len(counts)
    else:
        proportions = counts / total

    return {
        "bin_edges": [float(x) for x in bin_edges],
        "proportions": [float(x) for x in proportions],
    }


def _categorical_reference(series: pd.Series) -> dict[str, float]:
    """Create reference category proportions."""
    counts = series.astype(str).value_counts(dropna=False)
    total = counts.sum()

    if total == 0:
        return {}

    return {str(category): float(count / total) for category, count in counts.items()}


def build_reference_statistics(
    *,
    X_reference: pd.DataFrame,
    reference_scores,
    threshold: float,
) -> dict[str, Any]:
    """Build reference statistics from the training split."""
    reference_scores = np.asarray(reference_scores)
    reference_predictions = (reference_scores >= threshold).astype(int)

    numeric_stats = {
        column: _numeric_reference(X_reference[column])
        for column in NUMERIC_COLUMNS
        if column in X_reference.columns
    }

    categorical_stats = {
        column: _categorical_reference(X_reference[column])
        for column in CATEGORICAL_COLUMNS
        if column in X_reference.columns
    }

    return {
        "numeric": numeric_stats,
        "categorical": categorical_stats,
        "output": {
            "positive_prediction_rate": float(reference_predictions.mean()),
            "mean_score": float(reference_scores.mean()),
            "threshold": float(threshold),
        },
    }