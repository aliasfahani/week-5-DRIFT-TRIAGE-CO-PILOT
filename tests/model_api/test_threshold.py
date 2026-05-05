"""Tests for the operating threshold rule."""

import pytest

from services.model_api.app.ml.threshold import select_highest_threshold_for_recall


def test_selects_highest_threshold_that_meets_recall():
    y_true = [1, 1, 1, 1, 0]
    y_score = [0.9, 0.8, 0.7, 0.2, 0.95]

    result = select_highest_threshold_for_recall(y_true, y_score, min_recall=0.75)

    assert result["threshold"] == pytest.approx(0.7)
    assert result["recall"] == pytest.approx(0.75)


def test_fails_when_no_threshold_meets_recall():
    with pytest.raises(ValueError, match="No threshold achieved"):
        select_highest_threshold_for_recall([0, 0], [0.1, 0.2], min_recall=0.75)
