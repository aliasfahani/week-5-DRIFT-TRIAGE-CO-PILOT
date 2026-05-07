"""Model fidelity replay test.

Guard against prediction path drift by verifying API predictor output matches
direct pipeline output to machine precision.
"""

from __future__ import annotations

import pytest

from services.model_api.app.predictor import ModelPredictor
from services.model_api.app.schemas import BankMarketingRequest


def _sample_request() -> BankMarketingRequest:
    return BankMarketingRequest(
        age=41,
        job="admin.",
        marital="married",
        education="university.degree",
        default="no",
        housing="yes",
        loan="no",
        contact="cellular",
        month="may",
        day_of_week="thu",
        campaign=2,
        pdays=999,
        previous=0,
        poutcome="nonexistent",
        **{
            "emp.var.rate": 1.1,
            "cons.price.idx": 93.994,
            "cons.conf.idx": -36.4,
            "euribor3m": 4.857,
            "nr.employed": 5191.0,
        },
    )


def test_prediction_fidelity_replay_1e_12():
    """Predictor response should match direct pipeline probability."""
    predictor = ModelPredictor()
    request = _sample_request()
    dataframe = predictor.request_to_dataframe(request)

    direct_probability = float(predictor.pipeline.predict_proba(dataframe)[:, 1][0])
    api_probability = float(predictor.predict(request)["probability"])

    assert api_probability == pytest.approx(direct_probability, abs=1e-12)
