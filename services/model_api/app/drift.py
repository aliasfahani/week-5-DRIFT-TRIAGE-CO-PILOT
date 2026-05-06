"""Drift report generation for recent predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chisquare

from services.model_api.app.ml.artifacts import REFERENCE_STATS_PATH, load_json
from services.model_api.app.ml.preprocess import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS
from services.model_api.app.predictor import PREDICTION_LOG_PATH


def _safe_proportions(counts: np.ndarray) -> np.ndarray:
    """Convert counts to proportions safely."""
    counts = counts.astype(float)
    total = counts.sum()

    if total == 0:
        return np.ones_like(counts) / len(counts)

    return counts / total


def population_stability_index(
    expected_proportions: list[float],
    actual_proportions: list[float],
) -> float:
    """Compute PSI between expected and actual distributions."""
    expected = np.asarray(expected_proportions, dtype=float)
    actual = np.asarray(actual_proportions, dtype=float)

    epsilon = 1e-6
    expected = np.clip(expected, epsilon, None)
    actual = np.clip(actual, epsilon, None)

    return float(np.sum((actual - expected) * np.log(actual / expected)))


def severity_from_psi(psi: float) -> str:
    """Convert PSI into severity."""
    if psi >= 0.25:
        return "high"
    if psi >= 0.10:
        return "medium"
    return "low"


def severity_from_p_value(p_value: float) -> str:
    """Convert chi-square p-value into severity."""
    if p_value < 0.01:
        return "high"
    if p_value < 0.05:
        return "medium"
    return "low"


def combine_severity(severities: list[str]) -> str:
    """Return the highest severity."""
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


def read_prediction_log(path: Path = PREDICTION_LOG_PATH) -> pd.DataFrame:
    """Read prediction JSONL file into a dataframe."""
    if not path.exists():
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            event = json.loads(line)
            row = dict(event["input"])
            row["probability"] = event["probability"]
            row["prediction"] = event["prediction"]
            row["created_at"] = event["created_at"]

            # Match training-time sentinel handling.
            row["pdays_was_999"] = int(row["pdays"] == 999)
            if row["pdays"] == 999:
                row["pdays"] = -1

            rows.append(row)

    return pd.DataFrame(rows)


def numeric_drift_report(
    *,
    current: pd.DataFrame,
    reference_stats: dict[str, Any],
) -> dict[str, Any]:
    """Calculate PSI for numeric features."""
    report = {}

    for column in NUMERIC_COLUMNS:
        if column not in current.columns:
            continue
        if column not in reference_stats["numeric"]:
            continue

        ref = reference_stats["numeric"][column]
        bin_edges = np.asarray(ref["bin_edges"], dtype=float)
        expected_proportions = ref["proportions"]

        values = pd.to_numeric(current[column], errors="coerce").dropna()

        if values.empty:
            continue

        counts, _ = np.histogram(values, bins=bin_edges)
        actual_proportions = _safe_proportions(counts)

        psi = population_stability_index(
            expected_proportions=expected_proportions,
            actual_proportions=actual_proportions.tolist(),
        )

        report[column] = {
            "psi": psi,
            "severity": severity_from_psi(psi),
        }

    return report


def categorical_drift_report(
    *,
    current: pd.DataFrame,
    reference_stats: dict[str, Any],
) -> dict[str, Any]:
    """Calculate chi-square drift report for categorical features."""
    report = {}

    for column in CATEGORICAL_COLUMNS:
        if column not in current.columns:
            continue
        if column not in reference_stats["categorical"]:
            continue

        reference_distribution = reference_stats["categorical"][column]
        categories = list(reference_distribution.keys())

        current_counts = current[column].astype(str).value_counts()
        observed = np.array([current_counts.get(category, 0) for category in categories], dtype=float)

        total_observed = observed.sum()
        if total_observed == 0:
            continue

        expected = np.array(
            [reference_distribution[category] * total_observed for category in categories],
            dtype=float,
        )

        # Avoid zero expected counts.
        expected = np.clip(expected, 1e-6, None)

        stat, p_value = chisquare(f_obs=observed, f_exp=expected)

        report[column] = {
            "chi_square": float(stat),
            "p_value": float(p_value),
            "severity": severity_from_p_value(float(p_value)),
        }

    return report


def output_drift_report(
    *,
    current: pd.DataFrame,
    reference_stats: dict[str, Any],
) -> dict[str, Any]:
    """Compare current output distribution with reference output distribution."""
    if current.empty or "prediction" not in current.columns:
        return {
            "severity": "low",
            "message": "No predictions available.",
        }

    reference_positive_rate = float(reference_stats["output"]["positive_prediction_rate"])
    current_positive_rate = float(current["prediction"].mean())
    difference = abs(current_positive_rate - reference_positive_rate)

    if difference >= 0.20:
        severity = "high"
    elif difference >= 0.10:
        severity = "medium"
    else:
        severity = "low"

    return {
        "reference_positive_prediction_rate": reference_positive_rate,
        "current_positive_prediction_rate": current_positive_rate,
        "absolute_difference": difference,
        "severity": severity,
    }


def generate_drift_report(window_size: int = 100) -> dict[str, Any]:
    """Generate a drift report over the most recent predictions."""
    if not REFERENCE_STATS_PATH.exists():
        raise FileNotFoundError(
            f"Reference stats not found at {REFERENCE_STATS_PATH}. "
            "Run training first."
        )

    current = read_prediction_log()

    if current.empty:
        return {
            "severity": "low",
            "window_size": 0,
            "message": "No predictions logged yet.",
            "numeric_drift": {},
            "categorical_drift": {},
            "output_drift": {},
        }

    current_window = current.tail(window_size)
    reference_stats = load_json(REFERENCE_STATS_PATH)

    numeric = numeric_drift_report(
        current=current_window,
        reference_stats=reference_stats,
    )
    categorical = categorical_drift_report(
        current=current_window,
        reference_stats=reference_stats,
    )
    output = output_drift_report(
        current=current_window,
        reference_stats=reference_stats,
    )

    severities = (
        [item["severity"] for item in numeric.values()]
        + [item["severity"] for item in categorical.values()]
        + [output.get("severity", "low")]
    )

    return {
        "severity": combine_severity(severities),
        "window_size": int(len(current_window)),
        "numeric_drift": numeric,
        "categorical_drift": categorical,
        "output_drift": output,
    }