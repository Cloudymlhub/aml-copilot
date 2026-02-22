"""
Counterparty Graph Computation — PySpark Implementation

Computes the full counterparty graph for a given case at Stage D (case assembly time).
All metrics are computed fresh from four source tables. No pre-materialized tables required.

Source Tables:
  - transactions: all customer transactions
  - risk_scores: daily risk scores per customer
  - labels: alert/case lifecycle per customer
  - kyc: customer KYC profile

Usage:
    context = CaseContext(
        customer_cif_id="CUST-12345",
        event_start=date(2025, 6, 1),
        event_end=date(2025, 8, 3),
        baseline_start=date(2025, 4, 1),
        baseline_end=date(2025, 5, 31),
        review_date=date(2025, 8, 5),
    )
    params = GraphParameters()  # uses defaults, override as needed

    graph = build_counterparty_graph(spark, transactions, risk_scores, labels, kyc, context, params)
    # graph is Dict[str, CounterpartyEntry]
    # serialize with: {k: v.model_dump() for k, v in graph.items()}
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Dict, List, Optional

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F


# =============================================================================
# ENUMS
# =============================================================================


class ActivityConsistency(str, Enum):
    REGULAR = "regular"
    INTERMITTENT = "intermittent"
    BURST = "burst"
    NEW = "new"
    DORMANT_REACTIVATED = "dormant_reactivated"


class CounterpartyType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"
    UNKNOWN = "unknown"


# =============================================================================
# INPUT MODELS
# =============================================================================


class CaseContext(BaseModel):
    """Defines the case being assembled — who, when, what windows."""

    customer_cif_id: str
    event_start: date
    event_end: date
    baseline_start: date
    baseline_end: date
    review_date: date


class GraphParameters(BaseModel):
    """
    All configurable parameters for the counterparty graph computation.
    Defaults match the spec. Override per deployment or per case.
    """

    score_lookback_months: int = Field(
        default=12, ge=3, le=36,
        description="Window for computing max risk score of internal counterparties",
    )
    lifetime_lookback_months: int = Field(
        default=12, ge=3, le=60,
        description="Window for computing lifetime transaction aggregates per relationship",
    )
    volume_spike_threshold: float = Field(
        default=2.0, ge=1.5, le=5.0,
        description="Event-vs-baseline ratio above which is_volume_spike is set to true",
    )
    hub_threshold: int = Field(
        default=10, ge=3, le=50,
        description="Minimum connected_customer_count for is_hub = true",
    )
    dormancy_gap_months: int = Field(
        default=3, ge=2, le=12,
        description="Months of inactivity before relationship is dormant_reactivated",
    )
    new_relationship_months: int = Field(
        default=3, ge=1, le=12,
        description="Relationships shorter than this are classified as new",
    )
    materiality_threshold: float = Field(
        default=50000, ge=10000, le=500000,
        description="Amount below which unknown counterparty is immaterial (AED)",
    )
    round_amount_pct_threshold: float = Field(
        default=0.50, ge=0.20, le=0.90,
        description="Percentage of round amounts above which pattern is flagged",
    )
    weighted_score_volume_window: int = Field(
        default=12, ge=3, le=36,
        description="Window for volumes used in external counterparty weighted avg score",
    )
    activity_regular_threshold: float = Field(
        default=0.70, ge=0.50, le=0.90,
        description="Months-active ratio above which activity_consistency = regular",
    )
    activity_intermittent_threshold: float = Field(
        default=0.30, ge=0.10, le=0.50,
        description="Months-active ratio above which activity_consistency = intermittent",
    )
    round_amount_modulo: int = Field(
        default=1000, ge=100, le=10000,
        description="Amount divisor for round-amount detection",
    )


# =============================================================================
# OUTPUT MODELS
# =============================================================================


class RelationshipProfile(BaseModel):
    """Edge properties: the relationship between customer and counterparty."""

    first_transaction_date: Optional[str] = None
    last_transaction_date: Optional[str] = None
    relationship_duration_months: int = 0
    months_active: int = 0
    is_new_in_event_period: bool = False
    is_bidirectional: bool = False
    activity_consistency: ActivityConsistency = ActivityConsistency.NEW


class LifetimeSummary(BaseModel):
    """Transaction aggregates over the full lifetime lookback window."""

    total_inbound_count: int = 0
    total_inbound_amount: float = 0.0
    total_outbound_count: int = 0
    total_outbound_amount: float = 0.0
    net_flow: float = 0.0
    avg_monthly_inbound: float = 0.0
    avg_monthly_outbound: float = 0.0


class EventPeriodAggregates(BaseModel):
    """Transaction aggregates within the event window."""

    inbound_count: int = 0
    inbound_amount: float = 0.0
    outbound_count: int = 0
    outbound_amount: float = 0.0
    round_amount_count: int = 0
    common_references: List[str] = Field(default_factory=list)
    common_descriptions: List[str] = Field(default_factory=list)
    reference_diversity: int = 0
    first_txn: Optional[str] = None
    last_txn: Optional[str] = None


class BaselinePeriodAggregates(BaseModel):
    """Transaction aggregates within the baseline window."""

    inbound_count: int = 0
    inbound_amount: float = 0.0
    outbound_count: int = 0
    outbound_amount: float = 0.0


class EventVsBaseline(BaseModel):
    """Per-counterparty comparison of event period to baseline."""

    inbound_amount_change: Optional[float] = None
    outbound_amount_change: Optional[float] = None
    is_volume_spike: bool = False
    is_entirely_new: bool = False


class ComplianceOwn(BaseModel):
    """Counterparty's own compliance history (from labels on their cif_id)."""

    own_alert_count: int = 0
    own_sar_count: int = 0
    own_rfi_count: int = 0
    own_prior_clearance_count: int = 0
    own_last_clearance_date: Optional[str] = None


class ComplianceConnected(BaseModel):
    """Compliance signals from counterparty's 1-hop network."""

    connected_sar_customer_count: int = 0
    connected_alert_customer_count: int = 0
    connected_case_open_count: int = 0


class NetworkPosition(BaseModel):
    """Counterparty's position in the transaction network."""

    connected_customer_count: int = 0
    is_hub: bool = False
    hub_score: float = 0.0


class InternalProfile(BaseModel):
    """Fields available only for internal counterparties (our customers)."""

    internal_customer_id: str
    internal_max_score: Optional[float] = None
    internal_risk_rating: Optional[str] = None
    internal_segment: Optional[str] = None
    internal_declared_income: Optional[float] = None


class ExternalProfile(BaseModel):
    """Fields available only for external counterparties."""

    weighted_avg_score: Optional[float] = None
    connected_high_risk_count: int = 0


class CounterpartyProfile(BaseModel):
    """Full node properties for a counterparty."""

    is_internal_customer: bool
    counterparty_type: CounterpartyType = CounterpartyType.UNKNOWN

    # Network
    network: NetworkPosition = Field(default_factory=NetworkPosition)

    # Compliance
    compliance_own: ComplianceOwn = Field(default_factory=ComplianceOwn)
    compliance_connected: ComplianceConnected = Field(default_factory=ComplianceConnected)

    # Prior clearance (unavailable in v1)
    has_prior_clearance: bool = False
    clearance_conditions: Optional[str] = None

    # Type-specific profile (one will be populated)
    internal: Optional[InternalProfile] = None
    external: Optional[ExternalProfile] = None


class CounterpartyEntry(BaseModel):
    """
    Complete counterparty data for the case JSON.
    One entry per counterparty in the graph.
    """

    counterparty_account: str
    counterparty_name: str
    relationship: RelationshipProfile
    lifetime_summary: LifetimeSummary
    event_period: EventPeriodAggregates
    baseline_period: BaselinePeriodAggregates
    event_vs_baseline: EventVsBaseline
    counterparty_profile: CounterpartyProfile


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def build_counterparty_graph(
    spark: SparkSession,
    transactions: DataFrame,
    risk_scores: DataFrame,
    labels: DataFrame,
    kyc: DataFrame,
    context: CaseContext,
    params: GraphParameters = GraphParameters(),
) -> Dict[str, CounterpartyEntry]:
    """
    Build the complete counterparty graph for a single case.

    Returns a dictionary keyed by counterparty_name, where each value
    is a validated CounterpartyEntry.
    """
    lifetime_start = context.review_date - relativedelta(months=params.lifetime_lookback_months)
    score_lookback_start = context.review_date - relativedelta(months=params.score_lookback_months)

    # ---- STEP 1: Customer transactions within lifetime window ----
    customer_txns = (
        transactions
        .filter(F.col("cif_id") == context.customer_cif_id)
        .filter(F.col("transaction_date").between(lifetime_start, context.review_date))
    )

    counterparties_df = (
        customer_txns
        .select("counterparty_bank_account", "counterparty_name", "counterparty_cif_id")
        .dropDuplicates(["counterparty_bank_account"])
    )

    # ---- STEP 2: Relationship profiles ----
    relationship_df = _compute_relationship_profile(
        customer_txns, context.event_start, context.event_end, params
    )

    # ---- STEP 3: Window aggregates ----
    lifetime_df = _compute_window_aggregates(
        customer_txns, lifetime_start, context.review_date,
        prefix="lt", params=params, include_references=False,
    )
    event_df = _compute_window_aggregates(
        customer_txns, context.event_start, context.event_end,
        prefix="ev", params=params, include_references=True,
    )
    baseline_df = _compute_window_aggregates(
        customer_txns, context.baseline_start, context.baseline_end,
        prefix="bl", params=params, include_references=False,
    )

    # ---- STEP 4: Event vs baseline ----
    evb_df = _compute_event_vs_baseline(event_df, baseline_df, params.volume_spike_threshold)

    # ---- STEP 5: Network properties (hits full transactions table) ----
    cp_accounts = [r.counterparty_bank_account for r in counterparties_df.collect()]
    network_df = _compute_network_properties(transactions, cp_accounts, params.hub_threshold)

    # ---- STEP 6: Risk scores ----
    score_df = _compute_risk_scores(
        transactions, risk_scores, counterparties_df,
        score_lookback_start, context.review_date, params.weighted_score_volume_window,
    )

    # ---- STEP 7: Compliance metrics ----
    compliance_df = _compute_compliance_metrics(
        transactions, labels, counterparties_df,
        context.event_start, context.event_end,
    )

    # ---- STEP 8: Connected high-risk count (KYC join for external CPs) ----
    high_risk_df = _compute_connected_high_risk(
        transactions, kyc, cp_accounts,
    )

    # ---- STEP 9: Internal KYC profile ----
    kyc_df = _compute_internal_kyc(kyc, counterparties_df)

    # ---- STEP 10: Join and assemble ----
    full = (
        counterparties_df
        .join(relationship_df, on=_CP, how="left")
        .join(lifetime_df, on=_CP, how="left")
        .join(event_df, on=_CP, how="left")
        .join(baseline_df, on=_CP, how="left")
        .join(evb_df, on=_CP, how="left")
        .join(network_df, on=_CP, how="left")
        .join(score_df, on=_CP, how="left")
        .join(compliance_df, on=_CP, how="left")
        .join(high_risk_df, on=_CP, how="left")
        .join(kyc_df, on=_CP, how="left")
    )

    return _assemble_graph(full, lifetime_start, context.review_date, params)


# =============================================================================
# INTERNAL CONSTANTS
# =============================================================================

_CP = "counterparty_bank_account"

_COMPANY_KEYWORDS = frozenset([
    "LLC", "LTD", "INC", "CORP", "CO.", "COMPANY", "GROUP",
    "TRADING", "REAL ESTATE", "BANK", "HOLDINGS", "ENTERPRISES",
    "FZE", "FZC", "FZCO",  # UAE free zone designations
])


# =============================================================================
# STEP 2: RELATIONSHIP PROFILE
# =============================================================================


def _compute_relationship_profile(
    customer_txns: DataFrame,
    event_start: date,
    event_end: date,
    params: GraphParameters,
) -> DataFrame:

    base = customer_txns.groupBy(_CP).agg(
        F.min("transaction_date").alias("first_transaction_date"),
        F.max("transaction_date").alias("last_transaction_date"),
        F.countDistinct(F.date_format("transaction_date", "yyyy-MM")).alias("months_active"),
        F.max(F.when(F.col("direction") == "credit", 1).otherwise(0)).alias("_has_cr"),
        F.max(F.when(F.col("direction") == "debit", 1).otherwise(0)).alias("_has_dr"),
    )

    base = (
        base
        .withColumn(
            "relationship_duration_months",
            F.months_between(
                F.col("last_transaction_date").cast("timestamp"),
                F.col("first_transaction_date").cast("timestamp"),
            ).cast("int"),
        )
        .withColumn(
            "is_new_in_event_period",
            F.col("first_transaction_date") >= F.lit(event_start),
        )
        .withColumn(
            "is_bidirectional",
            (F.col("_has_cr") == 1) & (F.col("_has_dr") == 1),
        )
        .drop("_has_cr", "_has_dr")
    )

    # Activity consistency classification
    span = F.greatest(F.col("relationship_duration_months"), F.lit(1))
    ratio = F.col("months_active") / span

    base = base.withColumn(
        "activity_consistency",
        F.when(
            F.col("relationship_duration_months") < params.new_relationship_months,
            F.lit(ActivityConsistency.NEW.value),
        )
        .when(ratio >= params.activity_regular_threshold, F.lit(ActivityConsistency.REGULAR.value))
        .when(ratio >= params.activity_intermittent_threshold, F.lit(ActivityConsistency.INTERMITTENT.value))
        .otherwise(F.lit(ActivityConsistency.BURST.value)),
    )

    # Override with dormant_reactivated where applicable
    dormancy = _detect_dormancy(customer_txns, params.dormancy_gap_months)
    base = (
        base
        .join(dormancy, on=_CP, how="left")
        .withColumn(
            "activity_consistency",
            F.when(
                F.col("_has_dormancy") == True,
                F.lit(ActivityConsistency.DORMANT_REACTIVATED.value),
            ).otherwise(F.col("activity_consistency")),
        )
        .drop("_has_dormancy")
    )

    return base


def _detect_dormancy(customer_txns: DataFrame, gap_months: int) -> DataFrame:
    """Flag counterparties with inactive gaps >= gap_months followed by resumed activity."""

    monthly = (
        customer_txns
        .withColumn("_md", F.to_date(F.date_format("transaction_date", "yyyy-MM-01")))
        .select(_CP, "_md")
        .dropDuplicates()
    )

    w = Window.partitionBy(_CP).orderBy("_md")
    monthly = monthly.withColumn("_prev", F.lag("_md").over(w))
    monthly = monthly.withColumn(
        "_gap",
        F.when(
            F.col("_prev").isNotNull(),
            F.months_between(F.col("_md").cast("timestamp"), F.col("_prev").cast("timestamp")),
        ).otherwise(0),
    )

    return (
        monthly
        .filter(F.col("_gap") >= gap_months)
        .select(_CP)
        .dropDuplicates()
        .withColumn("_has_dormancy", F.lit(True))
    )


# =============================================================================
# STEP 3: WINDOW AGGREGATES
# =============================================================================


def _compute_window_aggregates(
    customer_txns: DataFrame,
    window_start: date,
    window_end: date,
    prefix: str,
    params: GraphParameters,
    include_references: bool = False,
) -> DataFrame:

    windowed = customer_txns.filter(F.col("transaction_date").between(window_start, window_end))

    agg_exprs = [
        F.sum(F.when(F.col("direction") == "credit", 1).otherwise(0)).alias(f"{prefix}_in_count"),
        F.sum(F.when(F.col("direction") == "credit", F.col("amount")).otherwise(0)).alias(f"{prefix}_in_amt"),
        F.sum(F.when(F.col("direction") == "debit", 1).otherwise(0)).alias(f"{prefix}_out_count"),
        F.sum(F.when(F.col("direction") == "debit", F.col("amount")).otherwise(0)).alias(f"{prefix}_out_amt"),
    ]

    if include_references:
        agg_exprs.extend([
            F.sum(
                F.when(F.col("amount") % params.round_amount_modulo == 0, 1).otherwise(0)
            ).alias(f"{prefix}_round_count"),
            F.min("transaction_date").alias(f"{prefix}_first_txn"),
            F.max("transaction_date").alias(f"{prefix}_last_txn"),
            F.countDistinct("transaction_type").alias(f"{prefix}_ref_diversity"),
        ])

    result = windowed.groupBy(_CP).agg(*agg_exprs)

    # Net flow
    result = result.withColumn(
        f"{prefix}_net",
        F.coalesce(F.col(f"{prefix}_in_amt"), F.lit(0))
        - F.coalesce(F.col(f"{prefix}_out_amt"), F.lit(0)),
    )

    # Lifetime-specific: monthly averages
    if prefix == "lt":
        months = max(
            (window_end.year - window_start.year) * 12
            + window_end.month - window_start.month,
            1,
        )
        result = (
            result
            .withColumn(f"{prefix}_avg_m_in", F.col(f"{prefix}_in_amt") / F.lit(months))
            .withColumn(f"{prefix}_avg_m_out", F.col(f"{prefix}_out_amt") / F.lit(months))
        )

    # Top-N references and descriptions for event period
    if include_references:
        ref_top = _top_n_values(windowed, _CP, "transaction_type", 3, f"{prefix}_common_refs")
        desc_top = _top_n_values(windowed, _CP, "description", 3, f"{prefix}_common_descs")
        result = result.join(ref_top, on=_CP, how="left").join(desc_top, on=_CP, how="left")

    return result


def _top_n_values(
    df: DataFrame, group_col: str, value_col: str, n: int, alias: str,
) -> DataFrame:
    """Return top-N most frequent non-null values per group as a list column."""

    filtered = df.filter(F.col(value_col).isNotNull())

    counted = filtered.groupBy(group_col, value_col).count()
    w = Window.partitionBy(group_col).orderBy(F.desc("count"))

    return (
        counted
        .withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") <= n)
        .groupBy(group_col)
        .agg(F.collect_list(value_col).alias(alias))
    )


# =============================================================================
# STEP 4: EVENT VS BASELINE
# =============================================================================


def _compute_event_vs_baseline(
    event_df: DataFrame,
    baseline_df: DataFrame,
    spike_threshold: float,
) -> DataFrame:

    combined = event_df.select(
        _CP, "ev_in_amt", "ev_out_amt",
    ).join(
        baseline_df.select(_CP, "bl_in_amt", "bl_out_amt"),
        on=_CP,
        how="left",
    )

    bl_in = F.coalesce(F.col("bl_in_amt"), F.lit(0))
    bl_out = F.coalesce(F.col("bl_out_amt"), F.lit(0))

    return (
        combined
        .withColumn(
            "evb_in_change",
            F.when(bl_in > 0, F.round(F.col("ev_in_amt") / bl_in, 2)),
        )
        .withColumn(
            "evb_out_change",
            F.when(bl_out > 0, F.round(F.col("ev_out_amt") / bl_out, 2)),
        )
        .withColumn("evb_is_new", (bl_in == 0) & (bl_out == 0))
        .withColumn(
            "evb_is_spike",
            (F.coalesce(F.col("evb_in_change"), F.lit(0)) >= spike_threshold)
            | (F.coalesce(F.col("evb_out_change"), F.lit(0)) >= spike_threshold),
        )
        .select(_CP, "evb_in_change", "evb_out_change", "evb_is_spike", "evb_is_new")
    )


# =============================================================================
# STEP 5: NETWORK PROPERTIES
# =============================================================================


def _compute_network_properties(
    all_transactions: DataFrame,
    counterparty_accounts: List[str],
    hub_threshold: int,
) -> DataFrame:

    cp_txns = (
        all_transactions
        .filter(F.col(_CP).isin(counterparty_accounts))
        .groupBy(_CP)
        .agg(F.countDistinct("cif_id").alias("net_cust_count"))
    )

    avg_conn = (cp_txns.agg(F.avg("net_cust_count")).collect()[0][0]) or 1.0

    return (
        cp_txns
        .withColumn("net_is_hub", F.col("net_cust_count") >= hub_threshold)
        .withColumn("net_hub_score", F.round(F.col("net_cust_count") / F.lit(avg_conn), 2))
    )


# =============================================================================
# STEP 6: RISK SCORES
# =============================================================================


def _compute_risk_scores(
    all_transactions: DataFrame,
    risk_scores: DataFrame,
    counterparties_df: DataFrame,
    score_start: date,
    review_date: date,
    volume_window_months: int,
) -> DataFrame:

    # Max score per cif in lookback window
    max_scores = (
        risk_scores
        .filter(F.col("score_date").between(score_start, review_date))
        .groupBy("cif_id")
        .agg(F.max("score").alias("_max_score"))
    )

    # Internal: direct lookup
    internal = counterparties_df.filter(F.col("counterparty_cif_id").isNotNull())
    internal_scores = (
        internal
        .join(max_scores, internal.counterparty_cif_id == max_scores.cif_id, how="left")
        .select(F.col(_CP), F.col("_max_score").alias("sc_internal_max"))
    )

    # External: volume-weighted average
    external = counterparties_df.filter(F.col("counterparty_cif_id").isNull())
    ext_accounts = [r.counterparty_bank_account for r in external.collect()]

    if not ext_accounts:
        return internal_scores.withColumn("sc_weighted_avg", F.lit(None))

    vol_start = review_date - relativedelta(months=volume_window_months)

    connected = (
        all_transactions
        .filter(F.col(_CP).isin(ext_accounts))
        .filter(F.col("transaction_date").between(vol_start, review_date))
        .groupBy(_CP, "cif_id")
        .agg(F.sum("amount").alias("_vol"))
    )

    weighted = (
        connected
        .join(max_scores, on="cif_id", how="left")
        .filter(F.col("_max_score").isNotNull())
        .groupBy(_CP)
        .agg(
            (F.sum(F.col("_max_score") * F.col("_vol")) / F.sum("_vol")).alias("sc_weighted_avg")
        )
    )

    return internal_scores.join(weighted, on=_CP, how="full_outer")


# =============================================================================
# STEP 7: COMPLIANCE METRICS
# =============================================================================


def _compute_compliance_metrics(
    all_transactions: DataFrame,
    labels: DataFrame,
    counterparties_df: DataFrame,
    event_start: date,
    event_end: date,
) -> DataFrame:

    # --- Own metrics (internal counterparties only) ---
    internal = counterparties_df.filter(F.col("counterparty_cif_id").isNotNull())

    own = (
        internal
        .join(labels, internal.counterparty_cif_id == labels.cif_id, how="left")
        .groupBy(_CP)
        .agg(
            F.sum(F.when(F.col("is_l1"), 1).otherwise(0)).alias("cm_own_alert"),
            F.sum(F.when(F.col("is_l2"), 1).otherwise(0)).alias("cm_own_sar"),
            F.sum(F.when(F.col("is_l1"), 1).otherwise(0)).alias("cm_own_rfi"),
            F.sum(
                F.when(F.col("is_l1") & ~F.col("is_l2"), 1).otherwise(0)
            ).alias("cm_own_clearance"),
            F.max(
                F.when(F.col("is_l1") & ~F.col("is_l2"), F.col("case_closed_date"))
            ).alias("cm_own_last_clear"),
        )
    )

    # --- Connected metrics (all counterparties) ---
    cp_accounts = [r.counterparty_bank_account for r in counterparties_df.collect()]

    connected_custs = (
        all_transactions
        .filter(F.col(_CP).isin(cp_accounts))
        .select(_CP, "cif_id")
        .dropDuplicates()
    )

    conn_with_labels = connected_custs.join(labels, on="cif_id", how="left")

    connected = (
        conn_with_labels
        .groupBy(_CP)
        .agg(
            F.countDistinct(F.when(F.col("is_l2"), F.col("cif_id"))).alias("cm_conn_sar"),
            F.countDistinct(F.when(F.col("is_l1"), F.col("cif_id"))).alias("cm_conn_alert"),
            F.countDistinct(
                F.when(
                    (F.col("alert_generated_date") <= event_end)
                    & (
                        F.col("case_closed_date").isNull()
                        | (F.col("case_closed_date") >= event_start)
                    ),
                    F.col("cif_id"),
                )
            ).alias("cm_conn_open"),
        )
    )

    return (
        counterparties_df
        .select(_CP)
        .join(own, on=_CP, how="left")
        .join(connected, on=_CP, how="left")
    )


# =============================================================================
# STEP 8: CONNECTED HIGH-RISK COUNT
# =============================================================================


def _compute_connected_high_risk(
    all_transactions: DataFrame,
    kyc: DataFrame,
    cp_accounts: List[str],
) -> DataFrame:
    """Count connected internal customers with risk_rating = 'high' per counterparty."""

    connected_custs = (
        all_transactions
        .filter(F.col(_CP).isin(cp_accounts))
        .select(_CP, "cif_id")
        .dropDuplicates()
    )

    with_kyc = connected_custs.join(
        kyc.select("cif_id", "risk_rating"), on="cif_id", how="left",
    )

    return (
        with_kyc
        .groupBy(_CP)
        .agg(
            F.countDistinct(
                F.when(F.col("risk_rating") == "high", F.col("cif_id"))
            ).alias("cm_conn_high_risk")
        )
    )


# =============================================================================
# STEP 9: INTERNAL KYC PROFILE
# =============================================================================


def _compute_internal_kyc(kyc: DataFrame, counterparties_df: DataFrame) -> DataFrame:

    internal = counterparties_df.filter(F.col("counterparty_cif_id").isNotNull())

    return (
        internal
        .join(kyc, internal.counterparty_cif_id == kyc.cif_id, how="left")
        .select(
            F.col(_CP),
            F.col("risk_rating").alias("kyc_risk_rating"),
            F.col("segment").alias("kyc_segment"),
            F.col("declared_income").alias("kyc_declared_income"),
        )
    )


# =============================================================================
# STEP 10: ASSEMBLE INTO OUTPUT MODELS
# =============================================================================


def _infer_counterparty_type(name: Optional[str]) -> CounterpartyType:
    if not name:
        return CounterpartyType.UNKNOWN
    upper = name.upper()
    if any(kw in upper for kw in _COMPANY_KEYWORDS):
        return CounterpartyType.COMPANY
    return CounterpartyType.INDIVIDUAL


def _assemble_graph(
    full: DataFrame,
    lifetime_start: date,
    review_date: date,
    params: GraphParameters,
) -> Dict[str, CounterpartyEntry]:

    rows = full.collect()
    graph: Dict[str, CounterpartyEntry] = {}

    for row in rows:
        r = row.asDict()

        cp_name = r["counterparty_name"]
        is_internal = r["counterparty_cif_id"] is not None

        # -- Build each sub-model --

        relationship = RelationshipProfile(
            first_transaction_date=_date_str(r.get("first_transaction_date")),
            last_transaction_date=_date_str(r.get("last_transaction_date")),
            relationship_duration_months=r.get("relationship_duration_months") or 0,
            months_active=r.get("months_active") or 0,
            is_new_in_event_period=bool(r.get("is_new_in_event_period")),
            is_bidirectional=bool(r.get("is_bidirectional")),
            activity_consistency=ActivityConsistency(r.get("activity_consistency", "new")),
        )

        lifetime_summary = LifetimeSummary(
            total_inbound_count=_int(r.get("lt_in_count")),
            total_inbound_amount=_float(r.get("lt_in_amt")),
            total_outbound_count=_int(r.get("lt_out_count")),
            total_outbound_amount=_float(r.get("lt_out_amt")),
            net_flow=_float(r.get("lt_net")),
            avg_monthly_inbound=_float(r.get("lt_avg_m_in")),
            avg_monthly_outbound=_float(r.get("lt_avg_m_out")),
        )

        event_period = EventPeriodAggregates(
            inbound_count=_int(r.get("ev_in_count")),
            inbound_amount=_float(r.get("ev_in_amt")),
            outbound_count=_int(r.get("ev_out_count")),
            outbound_amount=_float(r.get("ev_out_amt")),
            round_amount_count=_int(r.get("ev_round_count")),
            common_references=r.get("ev_common_refs") or [],
            common_descriptions=r.get("ev_common_descs") or [],
            reference_diversity=_int(r.get("ev_ref_diversity")),
            first_txn=_date_str(r.get("ev_first_txn")),
            last_txn=_date_str(r.get("ev_last_txn")),
        )

        baseline_period = BaselinePeriodAggregates(
            inbound_count=_int(r.get("bl_in_count")),
            inbound_amount=_float(r.get("bl_in_amt")),
            outbound_count=_int(r.get("bl_out_count")),
            outbound_amount=_float(r.get("bl_out_amt")),
        )

        event_vs_baseline = EventVsBaseline(
            inbound_amount_change=_float_or_none(r.get("evb_in_change")),
            outbound_amount_change=_float_or_none(r.get("evb_out_change")),
            is_volume_spike=bool(r.get("evb_is_spike")),
            is_entirely_new=bool(r.get("evb_is_new")),
        )

        network = NetworkPosition(
            connected_customer_count=_int(r.get("net_cust_count")),
            is_hub=bool(r.get("net_is_hub")),
            hub_score=_float(r.get("net_hub_score")),
        )

        compliance_own = ComplianceOwn(
            own_alert_count=_int(r.get("cm_own_alert")),
            own_sar_count=_int(r.get("cm_own_sar")),
            own_rfi_count=_int(r.get("cm_own_rfi")),
            own_prior_clearance_count=_int(r.get("cm_own_clearance")),
            own_last_clearance_date=_date_str(r.get("cm_own_last_clear")),
        )

        compliance_connected = ComplianceConnected(
            connected_sar_customer_count=_int(r.get("cm_conn_sar")),
            connected_alert_customer_count=_int(r.get("cm_conn_alert")),
            connected_case_open_count=_int(r.get("cm_conn_open")),
        )

        internal_profile = None
        external_profile = None

        if is_internal:
            internal_profile = InternalProfile(
                internal_customer_id=r["counterparty_cif_id"],
                internal_max_score=_float_or_none(r.get("sc_internal_max")),
                internal_risk_rating=r.get("kyc_risk_rating"),
                internal_segment=r.get("kyc_segment"),
                internal_declared_income=_float_or_none(r.get("kyc_declared_income")),
            )
        else:
            external_profile = ExternalProfile(
                weighted_avg_score=_float_or_none(r.get("sc_weighted_avg")),
                connected_high_risk_count=_int(r.get("cm_conn_high_risk")),
            )

        profile = CounterpartyProfile(
            is_internal_customer=is_internal,
            counterparty_type=_infer_counterparty_type(cp_name),
            network=network,
            compliance_own=compliance_own,
            compliance_connected=compliance_connected,
            has_prior_clearance=False,
            clearance_conditions=None,
            internal=internal_profile,
            external=external_profile,
        )

        entry = CounterpartyEntry(
            counterparty_account=r["counterparty_bank_account"],
            counterparty_name=cp_name,
            relationship=relationship,
            lifetime_summary=lifetime_summary,
            event_period=event_period,
            baseline_period=baseline_period,
            event_vs_baseline=event_vs_baseline,
            counterparty_profile=profile,
        )

        graph[cp_name] = entry

    return graph


# =============================================================================
# HELPERS
# =============================================================================


def _date_str(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, date):
        return val.isoformat()
    return str(val)


def _int(val) -> int:
    if val is None:
        return 0
    return int(val)


def _float(val) -> float:
    if val is None:
        return 0.0
    return round(float(val), 2)


def _float_or_none(val) -> Optional[float]:
    if val is None:
        return None
    return round(float(val), 4)
