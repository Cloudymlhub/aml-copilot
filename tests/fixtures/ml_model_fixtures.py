"""Mock ML model output fixtures for testing.

MOCK_DATA: All ML model outputs in this file are fixtures - Priority: HIGH

These fixtures provide realistic ML model outputs for testing the Compliance Expert
and Review Agent workflows without requiring an actual ML model.
"""

from typing import Dict, Any
from agents.state import MLModelOutput, DailyRiskScore, RedFlagDetail, FeatureContribution


# MOCK_DATA: Structuring scenario - Classic threshold avoidance pattern
STRUCTURING_SCENARIO: MLModelOutput = {
    "daily_risk_scores": [
        {"date": "2024-01-15", "risk_score": 0.75},
        {"date": "2024-01-16", "risk_score": 0.82},
        {"date": "2024-01-17", "risk_score": 0.85},
        {"date": "2024-01-18", "risk_score": 0.92},
        {"date": "2024-01-19", "risk_score": 0.89},
        {"date": "2024-01-20", "risk_score": 0.87},
    ],
    "feature_values": {
        "txn_count_last_30d": 47,
        "avg_txn_amount": 9850.50,
        "txn_count_near_threshold": 6,  # Transactions $9,000-$9,999
        "cash_deposit_frequency": "daily",
        "total_amount_30d": 59100.00,
        "unique_branch_count": 3,
        "txn_timing_pattern": "consistent",  # Same time each day
        "customer_profile_match": 0.3,  # Low match - unusual for stated business
    },
    "red_flag_scores": {
        "transactions_below_threshold": 0.95,
        "rapid_movement_of_funds": 0.23,
        "cash_intensive_business": 0.67,
        "inconsistent_with_business_profile": 0.71,
    },
    "most_likely_typology": "structuring",
    "typology_likelihoods": {
        "structuring": 0.85,
        "layering": 0.23,
        "trade_based_ml": 0.10,
        "shell_company": 0.15,
    },
    "typology_red_flags": {
        "structuring": [
            {
                "red_flag": "transactions_below_threshold",
                "score": 0.95,
                "contributing_features": [
                    {
                        "feature": "txn_count_near_threshold",
                        "value": 6,
                        "importance": 0.85,
                    },
                    {
                        "feature": "avg_txn_amount",
                        "value": 9850.50,
                        "importance": 0.78,
                    },
                    {
                        "feature": "total_amount_30d",
                        "value": 59100.00,
                        "importance": 0.72,
                    },
                ],
            },
            {
                "red_flag": "inconsistent_with_business_profile",
                "score": 0.71,
                "contributing_features": [
                    {
                        "feature": "customer_profile_match",
                        "value": 0.3,
                        "importance": 0.65,
                    },
                    {
                        "feature": "cash_deposit_frequency",
                        "value": "daily",
                        "importance": 0.58,
                    },
                ],
            },
        ]
    },
}


# MOCK_DATA: Layering scenario - Complex fund movement
LAYERING_SCENARIO: MLModelOutput = {
    "daily_risk_scores": [
        {"date": "2024-01-10", "risk_score": 0.45},
        {"date": "2024-01-11", "risk_score": 0.68},
        {"date": "2024-01-12", "risk_score": 0.79},
        {"date": "2024-01-13", "risk_score": 0.82},
    ],
    "feature_values": {
        "txn_count_last_30d": 89,
        "avg_txn_amount": 15420.75,
        "wire_transfer_count": 34,
        "rapid_movement_count": 12,  # Funds in and out within 48hrs
        "unique_counterparty_count": 23,
        "international_wire_count": 18,
        "high_risk_country_count": 4,
        "round_dollar_txn_count": 28,
        "avg_account_balance": 8500.00,  # Low relative to volume
    },
    "red_flag_scores": {
        "rapid_movement_of_funds": 0.88,
        "complex_transaction_structures": 0.82,
        "high_risk_geography": 0.76,
        "round_dollar_transactions": 0.69,
    },
    "most_likely_typology": "layering",
    "typology_likelihoods": {
        "layering": 0.79,
        "structuring": 0.35,
        "trade_based_ml": 0.42,
        "shell_company": 0.58,
    },
    "typology_red_flags": {
        "layering": [
            {
                "red_flag": "rapid_movement_of_funds",
                "score": 0.88,
                "contributing_features": [
                    {
                        "feature": "rapid_movement_count",
                        "value": 12,
                        "importance": 0.82,
                    },
                    {
                        "feature": "avg_account_balance",
                        "value": 8500.00,
                        "importance": 0.75,
                    },
                ],
            },
            {
                "red_flag": "complex_transaction_structures",
                "score": 0.82,
                "contributing_features": [
                    {
                        "feature": "unique_counterparty_count",
                        "value": 23,
                        "importance": 0.79,
                    },
                    {
                        "feature": "wire_transfer_count",
                        "value": 34,
                        "importance": 0.71,
                    },
                ],
            },
        ]
    },
}


# MOCK_DATA: Low risk scenario - Normal business activity
LOW_RISK_SCENARIO: MLModelOutput = {
    "daily_risk_scores": [
        {"date": "2024-01-15", "risk_score": 0.15},
        {"date": "2024-01-16", "risk_score": 0.18},
        {"date": "2024-01-17", "risk_score": 0.12},
        {"date": "2024-01-18", "risk_score": 0.16},
        {"date": "2024-01-19", "risk_score": 0.14},
    ],
    "feature_values": {
        "txn_count_last_30d": 23,
        "avg_txn_amount": 2340.50,
        "txn_count_near_threshold": 0,
        "cash_deposit_frequency": "weekly",
        "total_amount_30d": 28450.00,
        "customer_profile_match": 0.92,  # High match with expected behavior
        "velocity_change": 0.05,  # Minimal change from baseline
    },
    "red_flag_scores": {
        "transactions_below_threshold": 0.05,
        "rapid_movement_of_funds": 0.08,
        "inconsistent_with_business_profile": 0.12,
    },
    "most_likely_typology": None,  # No strong typology match
    "typology_likelihoods": {
        "structuring": 0.08,
        "layering": 0.12,
        "trade_based_ml": 0.05,
        "shell_company": 0.10,
    },
    "typology_red_flags": {},  # No significant red flags
}


# MOCK_DATA: Trade-based ML scenario - Invoice manipulation patterns
TRADE_BASED_ML_SCENARIO: MLModelOutput = {
    "daily_risk_scores": [
        {"date": "2024-01-01", "risk_score": 0.62},
        {"date": "2024-01-08", "risk_score": 0.71},
        {"date": "2024-01-15", "risk_score": 0.68},
        {"date": "2024-01-22", "risk_score": 0.74},
    ],
    "feature_values": {
        "international_trade_count": 45,
        "invoice_amount_variance": 0.78,  # High variance suggests manipulation
        "high_risk_country_trade": 12,
        "over_invoice_pattern_score": 0.82,
        "commodity_price_deviation": 0.65,  # Prices don't match market rates
        "shipping_doc_consistency": 0.34,  # Low consistency score
        "related_party_trade_count": 23,
    },
    "red_flag_scores": {
        "trade_finance_anomalies": 0.85,
        "high_risk_geography": 0.72,
        "shell_company_indicators": 0.58,
        "complex_transaction_structures": 0.63,
    },
    "most_likely_typology": "trade_based_ml",
    "typology_likelihoods": {
        "trade_based_ml": 0.73,
        "layering": 0.45,
        "structuring": 0.18,
        "shell_company": 0.52,
    },
    "typology_red_flags": {
        "trade_based_ml": [
            {
                "red_flag": "trade_finance_anomalies",
                "score": 0.85,
                "contributing_features": [
                    {
                        "feature": "over_invoice_pattern_score",
                        "value": 0.82,
                        "importance": 0.88,
                    },
                    {
                        "feature": "commodity_price_deviation",
                        "value": 0.65,
                        "importance": 0.76,
                    },
                    {
                        "feature": "shipping_doc_consistency",
                        "value": 0.34,
                        "importance": 0.71,
                    },
                ],
            }
        ]
    },
}


# MOCK_DATA: Missing data scenario - Insufficient information
INCOMPLETE_DATA_SCENARIO: MLModelOutput = {
    "daily_risk_scores": None,  # Missing trend data
    "feature_values": {
        "txn_count_last_30d": 15,
        # Many features missing
    },
    "red_flag_scores": {
        "transactions_below_threshold": 0.45,
    },
    "most_likely_typology": "structuring",
    "typology_likelihoods": {
        "structuring": 0.52,
    },
    "typology_red_flags": {
        "structuring": [
            {
                "red_flag": "transactions_below_threshold",
                "score": 0.45,
                "contributing_features": [],  # No feature details available
            }
        ]
    },
}


# Helper function to get scenario by name
def get_ml_scenario(scenario_name: str) -> MLModelOutput:
    """Get ML model output scenario by name.

    Args:
        scenario_name: Name of scenario ("structuring", "layering", "low_risk",
                       "trade_based_ml", "incomplete_data")

    Returns:
        MLModelOutput fixture

    Raises:
        ValueError: If scenario name not found
    """
    scenarios = {
        "structuring": STRUCTURING_SCENARIO,
        "layering": LAYERING_SCENARIO,
        "low_risk": LOW_RISK_SCENARIO,
        "trade_based_ml": TRADE_BASED_ML_SCENARIO,
        "incomplete_data": INCOMPLETE_DATA_SCENARIO,
    }

    if scenario_name not in scenarios:
        raise ValueError(
            f"Unknown scenario: {scenario_name}. "
            f"Available: {list(scenarios.keys())}"
        )

    return scenarios[scenario_name]


# Export all scenarios
__all__ = [
    "STRUCTURING_SCENARIO",
    "LAYERING_SCENARIO",
    "LOW_RISK_SCENARIO",
    "TRADE_BASED_ML_SCENARIO",
    "INCOMPLETE_DATA_SCENARIO",
    "get_ml_scenario",
]
