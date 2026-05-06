"""FastAPI application for the model service."""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException

from services.model_api.app.drift import generate_drift_report
from services.model_api.app.predictor import ModelPredictor
from services.model_api.app.schemas import (
    BankMarketingRequest,
    HealthResponse,
    PredictionResponse,
)

app = FastAPI(
    title="Drift Triage Co-Pilot Model API",
    version="0.1.0",
    description="Serves bank marketing predictions and drift reports.",
)


@lru_cache
def get_predictor() -> ModelPredictor:
    """Load predictor once and cache it."""
    return ModelPredictor()


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "model_api",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
def health():
    """Health endpoint."""
    try:
        get_predictor()
        return HealthResponse(status="ok", model_loaded=True)
    except Exception:
        return HealthResponse(status="degraded", model_loaded=False)


@app.post("/predict", response_model=PredictionResponse)
def predict(request: BankMarketingRequest):
    """Run one prediction."""
    try:
        predictor = get_predictor()
        result = predictor.predict(request)
        return PredictionResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {exc}",
        ) from exc


@app.get("/drift/report")
def drift_report(window_size: int = 100):
    """Generate a drift report from recent predictions."""
    try:
        return generate_drift_report(window_size=window_size)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc