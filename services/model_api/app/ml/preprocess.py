"""Preprocessing utilities for the UCI Bank Marketing dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET_COLUMN = "y"
RANDOM_STATE = 42
LEAKAGE_COLUMNS = ("duration",)

NUMERIC_COLUMNS = (
    "age",
    "campaign",
    "pdays",
    "previous",
    "emp.var.rate",
    "cons.price.idx",
    "cons.conf.idx",
    "euribor3m",
    "nr.employed",
    "pdays_was_999",
)

CATEGORICAL_COLUMNS = (
    "job",
    "marital",
    "education",
    "default",
    "housing",
    "loan",
    "contact",
    "month",
    "day_of_week",
    "poutcome",
)


def load_bank_marketing_csv(path: str | Path):
    """Load the semicolon-delimited bank marketing CSV."""
    return pd.read_csv(path, sep=";")


def prepare_features_and_target(dataframe):
    """Drop leakage columns, handle pdays sentinel values, and encode the target."""
    df = dataframe.copy()

    missing_columns = {TARGET_COLUMN, *NUMERIC_COLUMNS[:-1], *CATEGORICAL_COLUMNS} - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Dataset is missing required columns: {missing}")

    df["pdays_was_999"] = (df["pdays"] == 999).astype(int)
    df["pdays"] = df["pdays"].where(df["pdays"] != 999, -1)

    y = df[TARGET_COLUMN].map({"no": 0, "yes": 1})
    if y.isna().any():
        bad_values = sorted(df.loc[y.isna(), TARGET_COLUMN].dropna().unique())
        raise ValueError(f"Unexpected target values: {bad_values}")

    X = df.drop(columns=[TARGET_COLUMN, *LEAKAGE_COLUMNS], errors="ignore")
    return X, y.astype(int)


def build_preprocessing_classifier_pipeline():
    """Build the sklearn preprocessor + classifier pipeline."""
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, list(NUMERIC_COLUMNS)),
            ("cat", categorical_transformer, list(CATEGORICAL_COLUMNS)),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
