"""Test fixtures for AML Copilot testing.

This module provides mock data fixtures for testing various agent workflows
without requiring live databases or ML models.
"""

from .ml_model_fixtures import (
    STRUCTURING_SCENARIO,
    LAYERING_SCENARIO,
    LOW_RISK_SCENARIO,
    TRADE_BASED_ML_SCENARIO,
    INCOMPLETE_DATA_SCENARIO,
    get_ml_scenario,
)

__all__ = [
    "STRUCTURING_SCENARIO",
    "LAYERING_SCENARIO",
    "LOW_RISK_SCENARIO",
    "TRADE_BASED_ML_SCENARIO",
    "INCOMPLETE_DATA_SCENARIO",
    "get_ml_scenario",
]
