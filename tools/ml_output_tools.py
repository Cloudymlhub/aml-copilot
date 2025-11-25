"""ML Model Output Tools - Retrieve pre-computed ML features and risk scores.

MOCK_DATA: All ML outputs are from fixtures for development/testing - Priority: HIGH
"""

from langchain_core.tools import tool
from typing import Optional, Dict, Any

from db.services.data_service import data_service


@tool
def get_ml_risk_assessment(cif_no: str) -> Dict[str, Any]:
    """Get ML model risk assessment for a customer (typologies, red flags, features).

    MOCK_DATA: Returns fixture data during development. Will connect to ML service in production.

    This tool retrieves pre-computed ML model outputs including:
    - Daily risk score trends
    - Feature values (transaction patterns, volumes, etc.)
    - Red flag confidence scores
    - Typology likelihood assessments
    - Attribution chain (Typology → Red Flags → Features)

    The Compliance Expert interprets these outputs rather than computing features itself.

    Args:
        cif_no: Customer CIF number (e.g., "C000123")

    Returns:
        Dict containing ML model outputs:
        - daily_risk_scores: List of {date, risk_score} time series
        - feature_values: Dict of pre-computed feature values
        - red_flag_scores: Dict of red flag names → confidence scores
        - most_likely_typology: Top ML-identified typology
        - typology_likelihoods: Dict of typology → likelihood scores
        - typology_red_flags: Attribution chain explaining the assessment

    Example:
        >>> ml_output = get_ml_risk_assessment("C000123")
        >>> print(ml_output["most_likely_typology"])
        "structuring"
        >>> print(ml_output["red_flag_scores"]["transactions_below_threshold"])
        0.95
    """
    ml_output = data_service.get_ml_model_output(cif_no)

    if not ml_output:
        return {
            "error": f"No ML model output available for customer {cif_no}",
            "cif_no": cif_no,
        }

    return {
        "cif_no": cif_no,
        "ml_model_output": ml_output,
        "data_source": "MOCK_FIXTURE",  # Identifies this as fixture data
        "note": "ML outputs are from test fixtures during development",
    }


@tool
def get_feature_importance(cif_no: str, typology: Optional[str] = None) -> Dict[str, Any]:
    """Get feature importance scores for ML model predictions.

    MOCK_DATA: Returns fixture data during development.

    Explains which features contributed most to the ML model's assessment.
    Useful for understanding WHY the model flagged a customer.

    Args:
        cif_no: Customer CIF number
        typology: Optional typology to get features for (e.g., "structuring").
                 If None, returns features for most likely typology.

    Returns:
        Dict containing:
        - typology: The typology being explained
        - top_features: List of features with importance scores
        - red_flags: Red flags triggered by these features

    Example:
        >>> importance = get_feature_importance("C000123", "structuring")
        >>> for feature in importance["top_features"]:
        ...     print(f"{feature['feature']}: {feature['importance']}")
    """
    ml_output = data_service.get_ml_model_output(cif_no)

    if not ml_output:
        return {
            "error": f"No ML model output available for customer {cif_no}",
            "cif_no": cif_no,
        }

    # Use specified typology or most likely one
    target_typology = typology or ml_output.get("most_likely_typology")

    if not target_typology:
        return {
            "error": "No typology specified and no most_likely_typology in ML output",
            "cif_no": cif_no,
        }

    # Get red flags for this typology
    typology_red_flags = ml_output.get("typology_red_flags", {})
    red_flags_list = typology_red_flags.get(target_typology, [])

    # Extract all features with importance scores
    all_features = []
    for red_flag_detail in red_flags_list:
        for feature in red_flag_detail.get("contributing_features", []):
            all_features.append({
                "feature": feature["feature"],
                "value": feature["value"],
                "importance": feature["importance"],
                "red_flag": red_flag_detail["red_flag"],
            })

    # Sort by importance (descending)
    all_features.sort(key=lambda x: x["importance"], reverse=True)

    return {
        "cif_no": cif_no,
        "typology": target_typology,
        "typology_likelihood": ml_output.get("typology_likelihoods", {}).get(target_typology),
        "top_features": all_features[:10],  # Top 10 features
        "red_flags": [rf["red_flag"] for rf in red_flags_list],
        "data_source": "MOCK_FIXTURE",
    }
