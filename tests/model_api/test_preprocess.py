"""Tests for dataset preprocessing rules."""

import pandas as pd

from services.model_api.app.ml.preprocess import prepare_features_and_target


def sample_dataframe():
    return pd.DataFrame(
        {
            "age": [40, 30],
            "job": ["admin.", "unknown"],
            "marital": ["married", "single"],
            "education": ["university.degree", "unknown"],
            "default": ["no", "unknown"],
            "housing": ["yes", "no"],
            "loan": ["no", "yes"],
            "contact": ["cellular", "telephone"],
            "month": ["may", "jun"],
            "day_of_week": ["mon", "tue"],
            "duration": [100, 200],
            "campaign": [1, 2],
            "pdays": [999, 6],
            "previous": [0, 1],
            "poutcome": ["nonexistent", "success"],
            "emp.var.rate": [1.1, -1.8],
            "cons.price.idx": [93.994, 92.893],
            "cons.conf.idx": [-36.4, -46.2],
            "euribor3m": [4.857, 1.299],
            "nr.employed": [5191.0, 5099.1],
            "y": ["no", "yes"],
        }
    )


def test_duration_is_dropped():
    X, _ = prepare_features_and_target(sample_dataframe())
    assert "duration" not in X.columns


def test_unknown_is_preserved_as_category():
    X, _ = prepare_features_and_target(sample_dataframe())
    assert "unknown" in set(X["job"])
    assert "unknown" in set(X["education"])


def test_pdays_999_gets_flagged():
    X, _ = prepare_features_and_target(sample_dataframe())
    assert X["pdays_was_999"].tolist() == [1, 0]
    assert X["pdays"].tolist() == [-1, 6]
