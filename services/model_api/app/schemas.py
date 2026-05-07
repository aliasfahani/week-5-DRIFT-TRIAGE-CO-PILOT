"""Pydantic schemas for the model API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BankMarketingRequest(BaseModel):
    """Raw bank marketing prediction request.

    Field aliases preserve the original UCI column names such as emp.var.rate.
    """

    model_config = ConfigDict(populate_by_name=True)

    age: int = Field(..., ge=18, le=100)
    job: str
    marital: str
    education: str
    default: str
    housing: str
    loan: str
    contact: str
    month: str
    day_of_week: str
    campaign: int = Field(..., ge=1)
    pdays: int = Field(..., ge=0)
    previous: int = Field(..., ge=0)
    poutcome: str

    emp_var_rate: float = Field(..., alias="emp.var.rate")
    cons_price_idx: float = Field(..., alias="cons.price.idx")
    cons_conf_idx: float = Field(..., alias="cons.conf.idx")
    euribor3m: float
    nr_employed: float = Field(..., alias="nr.employed")


class PredictionResponse(BaseModel):
    """Prediction response returned by the API."""

    probability: float
    prediction: int
    threshold: float
    model_name: str
    model_version: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool


class PromotionChecklist(BaseModel):
    """Checklist required before promotion to Production."""

    model_artifact_exists: bool
    schema_validated: bool
    model_card_present: bool
    threshold_selected: bool
    reference_stats_present: bool
    tests_passed: bool
    human_approved: bool


class PromotionRequest(BaseModel):
    """Programmatic request to promote a model to Production."""

    model_name: str = "bank_marketing_classifier"
    model_version: str = "local-artifact"
    model_uri: str = "artifacts/model_api/model.joblib"
    requested_by: Literal["agent"]
    approval_id: str
    checklist: PromotionChecklist
    requested_action: Literal["retrain_candidate", "rollback_candidate"] | None = None


class PromotionResponse(BaseModel):
    """Promotion result payload."""

    model_name: str
    model_version: str
    model_uri: str
    stage: str
    promoted_at: str
    requested_by: str
    approval_id: str
    requested_action: str | None = None
    model_card: dict[str, Any]