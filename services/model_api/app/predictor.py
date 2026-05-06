"""Prediction helper for the FastAPI service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from services.model_api.app.ml.artifacts import (
    MODEL_CARD_PATH,
    load_json,
    load_model,
    load_threshold,
)
from services.model_api.app.schemas import BankMarketingRequest

RUNTIME_DIR = Path("runtime")
PREDICTION_LOG_PATH = RUNTIME_DIR / "predictions_log.jsonl"


class ModelPredictor:
    """Loads artifacts and serves predictions."""

    def __init__(self) -> None:
        self.pipeline = load_model()
        self.threshold = load_threshold()

        if MODEL_CARD_PATH.exists():
            self.model_card = load_json(MODEL_CARD_PATH)
        else:
            self.model_card = {"model_name": "bank_marketing_classifier"}

    @staticmethod
    def request_to_dataframe(request: BankMarketingRequest) -> pd.DataFrame:
        """Convert a validated Pydantic request into a model-ready DataFrame."""
        raw = request.model_dump(by_alias=True)

        # Recreate the same feature engineering used in training.
        raw["pdays_was_999"] = int(raw["pdays"] == 999)
        if raw["pdays"] == 999:
            raw["pdays"] = -1

        return pd.DataFrame([raw])

    def predict(self, request: BankMarketingRequest) -> dict[str, Any]:
        """Predict probability and class for one request."""
        X = self.request_to_dataframe(request)

        probability = float(self.pipeline.predict_proba(X)[:, 1][0])
        prediction = int(probability >= self.threshold)

        response = {
            "probability": probability,
            "prediction": prediction,
            "threshold": self.threshold,
            "model_name": self.model_card.get("model_name", "bank_marketing_classifier"),
            "model_version": "local-artifact",
        }

        self.log_prediction(request=request, response=response)
        return response

    def log_prediction(
        self,
        *,
        request: BankMarketingRequest,
        response: dict[str, Any],
    ) -> None:
        """Append prediction event to a local JSONL file."""
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input": request.model_dump(by_alias=True),
            "probability": response["probability"],
            "prediction": response["prediction"],
            "threshold": response["threshold"],
            "model_name": response["model_name"],
            "model_version": response["model_version"],
        }

        with PREDICTION_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")