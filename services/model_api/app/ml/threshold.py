"""Operating-threshold selection for binary classifiers."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import recall_score


def select_highest_threshold_for_recall(y_true, y_score, min_recall: float = 0.75):
    """Return the highest threshold whose recall is at least min_recall."""
    if not 0 <= min_recall <= 1:
        raise ValueError("min_recall must be between 0 and 1")

    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    if y_true.shape[0] != y_score.shape[0]:
        raise ValueError("y_true and y_score must have the same length")

    thresholds = np.unique(np.concatenate(([0.0, 1.0], y_score)))
    thresholds.sort()
    valid_thresholds = []
    for threshold in thresholds:
        y_pred = (y_score >= threshold).astype(int)
        recall = recall_score(y_true, y_pred, zero_division=0)
        if recall >= min_recall:
            valid_thresholds.append((threshold, recall))

    if not valid_thresholds:
        raise ValueError(f"No threshold achieved recall >= {min_recall}")

    selected_threshold, selected_recall = valid_thresholds[-1]
    return {
        "threshold": float(selected_threshold),
        "recall": float(selected_recall),
        "min_recall": float(min_recall),
    }
