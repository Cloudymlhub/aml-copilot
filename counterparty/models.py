"""
Data models for the Counterparty Graph module.

All models use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# INPUT MODELS
# =============================================================================


class CaseContext(BaseModel):
    """Input context for a single case under review."""

    cif_no: str
    review_date: date
    event_start: Optional[date] = None
    event_end: Optional[date] = None
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None


class GraphParameters(BaseModel):
    """Tunable parameters for graph computation."""

    # Lookback windows (months from review_date)
    lifetime_lookback_months: int = 24
    network_lookback_months: int = 12
    rating_lookback_months: int = 12

    # Event/baseline defaults (months before review_date)
    default_event_months: int = 3
    default_baseline_months: int = 6  # baseline ends where event starts

    # Hub detection
    hub_threshold: int = 5

    # Volume spike detection
    volume_spike_threshold: float = 2.0  # event > baseline * threshold

    # Round amount detection
    round_amount_modulo: int = 1000

    # Risk score thresholds
    rating_high_threshold: float = 0.7
    rating_medium_threshold: float = 0.4

    # Weighted score volume window (months)
    weighted_score_volume_window: int = 6


# =============================================================================
# OUTPUT MODELS — Profile Components
# =============================================================================


class RelationshipProfile(BaseModel):
    """Temporal relationship characteristics."""

    first_transaction_date: Optional[str] = None
    last_transaction_date: Optional[str] = None
    relationship_duration_months: int = 0
    months_active: int = 0
    is_new_in_event_period: bool = False
    is_bidirectional: bool = False


class LifetimeSummary(BaseModel):
    """Aggregate transaction volumes over full lifetime window."""

    total_inbound_count: int = 0
    total_inbound_amount: float = 0.0
    total_outbound_count: int = 0
    total_outbound_amount: float = 0.0
    net_flow: float = 0.0


class EventPeriodAggregates(BaseModel):
    """Transaction volumes during event period."""

    inbound_count: int = 0
    inbound_amount: float = 0.0
    outbound_count: int = 0
    outbound_amount: float = 0.0
    round_amount_count: int = 0


class BaselinePeriodAggregates(BaseModel):
    """Transaction volumes during baseline period."""

    inbound_count: int = 0
    inbound_amount: float = 0.0
    outbound_count: int = 0
    outbound_amount: float = 0.0


class EventVsBaseline(BaseModel):
    """Comparison of event period vs baseline period."""

    inbound_amount_change: Optional[float] = None
    outbound_amount_change: Optional[float] = None
    is_volume_spike: bool = False
    is_entirely_new: bool = False


class NetworkPosition(BaseModel):
    """Network topology metrics for a counterparty."""

    connected_customer_count: int = 0
    is_hub: bool = False
    hub_score: float = 0.0


class ComplianceOwn(BaseModel):
    """Counterparty's own compliance history (internal only)."""

    own_alert_count: int = 0
    own_case_count: int = 0
    own_sar_count: int = 0
    own_has_open_case: bool = False
    own_prior_clearance_count: int = 0
    own_last_clearance_date: Optional[str] = None


class ComplianceConnected(BaseModel):
    """Compliance status of counterparty's connected customers."""

    connected_alert_customer_count: int = 0
    connected_case_customer_count: int = 0
    connected_sar_customer_count: int = 0
    connected_case_open_count: int = 0


class InternalProfile(BaseModel):
    """Profile for counterparties who are bank customers (resolved via account_master)."""

    internal_customer_id: Optional[str] = None
    internal_max_score: Optional[float] = None
    internal_risk_rating: Optional[str] = None
    internal_segment: Optional[str] = None
    internal_declared_income: Optional[float] = None


class ExternalProfile(BaseModel):
    """Profile for external counterparties (not in account_master)."""

    weighted_avg_score: Optional[float] = None


# =============================================================================
# OUTPUT MODELS — Counterparty Entry
# =============================================================================


class CounterpartyEntry(BaseModel):
    """Complete analysis of one counterparty relationship."""

    counterparty_account: str
    counterparty_name: str
    target_is_internal: bool = False

    # Relationship & temporal
    relationship: RelationshipProfile = Field(default_factory=RelationshipProfile)
    lifetime_summary: LifetimeSummary = Field(default_factory=LifetimeSummary)

    # Period analysis
    event_periods: Dict[str, EventPeriodAggregates] = Field(default_factory=dict)
    baseline_period: BaselinePeriodAggregates = Field(
        default_factory=BaselinePeriodAggregates
    )
    event_vs_baselines: Dict[str, EventVsBaseline] = Field(default_factory=dict)

    # Network & compliance
    network: NetworkPosition = Field(default_factory=NetworkPosition)
    compliance_own: ComplianceOwn = Field(default_factory=ComplianceOwn)
    compliance_connected: ComplianceConnected = Field(
        default_factory=ComplianceConnected
    )

    # Type-specific profile (one will be set)
    internal_profile: Optional[InternalProfile] = None
    external_profile: Optional[ExternalProfile] = None


# =============================================================================
# OUTPUT MODELS — Customer Graph
# =============================================================================


class CustomerProfile(BaseModel):
    """Reviewed customer's own profile."""

    cif_no: str
    score: Optional[float] = None
    risk_rating: Optional[str] = None
    segment: Optional[str] = None
    declared_income: Optional[float] = None
    alert_count: int = 0
    case_count: int = 0
    sar_count: int = 0
    has_open_case: bool = False


class CustomerSummary(BaseModel):
    """Quick stats for a customer's counterparty network."""

    total_counterparties: int = 0
    internal_count: int = 0
    external_count: int = 0
    hub_counterparties: int = 0
    high_risk_counterparties: int = 0


class CustomerGraph(BaseModel):
    """Complete analysis for one reviewed customer."""

    profile: CustomerProfile
    counterparties: Dict[str, CounterpartyEntry] = Field(default_factory=dict)
    summary: CustomerSummary = Field(default_factory=CustomerSummary)


# =============================================================================
# BATCH METRICS
# =============================================================================


@dataclass
class BatchMetrics:
    """Metrics from batch computation for monitoring."""

    total_customers: int = 0
    total_counterparties: int = 0
    unique_counterparties: int = 0
    shared_counterparties: int = 0
    transactions_scanned: int = 0

    # Step timing
    step_times: Dict[str, float] = field(default_factory=dict)
    compute_time_seconds: float = 0.0

    # Skip flags
    skipped_network: bool = False
    skipped_connected_compliance: bool = False

    def to_dict(self) -> dict:
        return {
            "total_customers": self.total_customers,
            "total_counterparties": self.total_counterparties,
            "unique_counterparties": self.unique_counterparties,
            "shared_counterparties": self.shared_counterparties,
            "transactions_scanned": self.transactions_scanned,
            "compute_time_seconds": round(self.compute_time_seconds, 2),
            "step_times": {k: round(v, 2) for k, v in self.step_times.items()},
            "skipped_network": self.skipped_network,
            "skipped_connected_compliance": self.skipped_connected_compliance,
        }
