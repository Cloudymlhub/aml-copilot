"""Customer data models with flexible feature groups.

Design Philosophy:
- Core models (CustomerBasic): Explicitly define all fields for type safety
- Feature group models: Minimal required fields + allow extras for ML features
- Why? ML features change frequently, Pydantic models should be flexible
- Source of truth for features: feature_catalog.json, not code
"""

from datetime import datetime, date
from typing import Optional, Any, Dict, Union
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class CustomerBasic(BaseModel):
    """Core customer identity and risk score.

    Use this for: Quick lookups, risk checks, basic profile display.
    Query cost: ~9 columns, minimal token usage for LLM context.

    Note: These fields are stable and rarely change, so we define them explicitly.
    """

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    cif_no: str
    name: str
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    kyc_status: Optional[str] = None
    account_opened_date: Optional[date] = None
    occupation: Optional[str] = None
    industry: Optional[str] = None
    risk_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomerFeatureGroup(BaseModel):
    """Base model for feature groups with flexible schema.

    Design: Only defines required field (cif_no), allows extras for ML features.
    Why? ML features change frequently based on feature engineering pipeline.
    Source of truth: feature_catalog.json defines all available features.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra='allow',  # Allow additional fields not explicitly defined
    )

    cif_no: str


class CustomerTransactionFeatures(CustomerFeatureGroup):
    """Transaction aggregation features across multiple time windows.

    Use this for: Volume analysis, transaction patterns, velocity checks.

    Example features (see feature_catalog.json for complete list):
    - sum_txn_count_w0_30, sum_txn_amount_w0_30, avg_txn_amount_w0_30
    - max_txn_amount_w0_90, std_txn_amount_w0_30
    - sum_txn_count_w30_60, avg_txn_amount_w30_60
    - max_single_txn_w0_180, sum_txn_amount_w0_180

    Note: Features are dynamically loaded from DB, validated by catalog, not code.
    """
    pass


class CustomerRiskFeatures(CustomerFeatureGroup):
    """Risk indicator features for AML pattern detection.

    Use this for: Typology detection (structuring, high-risk countries).

    Example features:
    - count_high_risk_countries_w0_90
    - count_cash_intensive_txn_w0_90
    - count_round_amount_txn_w0_90
    - ratio_international_txn_w0_90
    """
    pass


class CustomerBehavioralFeatures(CustomerFeatureGroup):
    """Behavioral pattern features for anomaly detection.

    Use this for: Channel analysis, transaction velocity, behavioral anomalies.

    Example features:
    - count_atm_withdrawals_w0_30
    - count_wire_transfers_w0_90
    - velocity_score_w0_30
    """
    pass


class CustomerNetworkFeatures(CustomerFeatureGroup):
    """Network/graph analysis features from relationship data.

    Use this for: Network analysis, community detection, counterparty risk.
    Source: Graph database or network analysis pipeline.

    Example features:
    - network_degree_centrality
    - network_community_id
    - count_unique_counterparties_w0_90
    - count_shared_counterparties
    """
    pass


class CustomerKnowledgeGraphFeatures(CustomerFeatureGroup):
    """Knowledge graph features from external entity resolution.

    Use this for: PEP screening, sanctions checking, adverse media analysis.
    Source: External knowledge graph or entity linking system.

    Example features:
    - pep_exposure_score
    - adverse_media_score
    - sanction_list_proximity
    """
    pass


class CustomerFull(CustomerBasic):
    """Complete customer profile with all features.

    Use this sparingly: Only when you truly need everything.
    Query cost: 40+ columns, high token usage.
    Prefer: Fetching specific feature groups based on use case.

    Note: This model allows extra fields for all ML features.
    The complete list is defined in feature_catalog.json, not here.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra='allow',  # Allow all ML features dynamically
    )


# Create/Update models for API operations
class CustomerCreate(BaseModel):
    """Model for creating a new customer.

    Note: Only core fields required at creation. ML features are computed later.
    """

    cif_no: str
    name: str
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    kyc_status: str = "pending"
    account_opened_date: Optional[date] = None
    occupation: Optional[str] = None
    industry: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Model for updating customer information.

    Note: All fields optional for partial updates.
    """

    name: Optional[str] = None
    kyc_status: Optional[str] = None
    occupation: Optional[str] = None
    industry: Optional[str] = None
    risk_score: Optional[float] = None


# Type hints for feature group data (for documentation)
# Actual fields are dynamic and come from feature_catalog.json
CustomerTransactionFeaturesDict = Dict[str, Union[int, float, Decimal]]
CustomerRiskFeaturesDict = Dict[str, Union[int, float]]
CustomerBehavioralFeaturesDict = Dict[str, Union[int, float]]
CustomerNetworkFeaturesDict = Dict[str, Union[int, float, str]]
CustomerKnowledgeGraphFeaturesDict = Dict[str, float]
