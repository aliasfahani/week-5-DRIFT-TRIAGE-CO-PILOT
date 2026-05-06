"""Pydantic schemas for the model API."""

from __future__ import annotations

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