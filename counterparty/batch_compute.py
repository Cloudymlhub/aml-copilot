"""
Batch Counterparty Graph Computation — PySpark Implementation

Computes counterparty graphs for MULTIPLE customers in a single pass.
This is 10-100x more efficient than calling build_counterparty_graph() per customer.

Key Optimizations:
1. Pre-filter transactions for all customers in one scan
2. Collect all counterparty accounts across all customers
3. Compute expensive metrics (network, compliance, high-risk) ONCE for all
4. Partition results back to each customer's graph

Usage:
    batch_contexts = [
        CaseContext(customer_cif_id="CUST-001", ...),
        CaseContext(customer_cif_id="CUST-002", ...),
        ...  # up to ~100 customers
    ]
    params = GraphParameters()

    results, metrics = build_counterparty_graphs_batch(
        spark, transactions, risk_scores, labels, kyc,
        batch_contexts, params,
        # Optional expensive computations (skip to save time)
        skip_network=True,              # Hub detection
        skip_connected_compliance=True, # Connected customers' alerts/SARs
        skip_connected_high_risk=True,  # Connected high-risk customers
    )
    # results is Dict[str, Dict[str, CounterpartyEntry]]
    # Outer key = customer_cif_id, inner key = counterparty_name
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from .compute import (
    CaseContext,
    GraphParameters,
    CounterpartyEntry,
    RelationshipProfile,
    LifetimeSummary,
    EventPeriodAggregates,
    BaselinePeriodAggregates,
    EventVsBaseline,
    NetworkPosition,
    ComplianceOwn,
    ComplianceConnected,
    InternalProfile,
    ExternalProfile,
    CounterpartyProfile,
    ActivityConsistency,
    CounterpartyType,
    _infer_counterparty_type,
)
from .cache import ComputeCache

logger = logging.getLogger(__name__)

# Column name constant
_CP = "counterparty_bank_account"


# =============================================================================
# BATCH METRICS
# =============================================================================


@dataclass
class BatchMetrics:
    """Metrics from batch computation for monitoring."""

    total_customers: int = 0
    total_counterparties: int = 0
    unique_counterparties: int = 0  # Across all customers
    shared_counterparties: int = 0  # Appearing in multiple customers

    transactions_scanned: int = 0

    # Step timing
    step_times: Dict[str, float] = field(default_factory=dict)
    compute_time_seconds: float = 0.0

    # Skip flags used
    skipped_network: bool = False
    skipped_connected_compliance: bool = False

    def to_dict(self) -> Dict:
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


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def build_counterparty_graphs_batch(
    spark: SparkSession,
    transactions: DataFrame,
    risk_scores: DataFrame,
    labels: DataFrame,
    kyc: DataFrame,
    contexts: List[CaseContext],
    params: GraphParameters = GraphParameters(),
    # === Optional expensive computations (skip to save time) ===
    skip_network: bool = False,
    skip_connected_compliance: bool = False,
    # === Caching ===
    cache_path: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, CounterpartyEntry]], BatchMetrics]:
    """
    Build counterparty graphs for multiple customers in a single batch.

    This is significantly more efficient than calling build_counterparty_graph()
    for each customer, especially for expensive network/compliance computations.

    Args:
        spark: SparkSession
        transactions: Transaction data (all customers)
            Schema: cif_no, transaction_date, counterparty_bank_account,
                    counterparty_name, counterparty_cif_id, direction, amount
        risk_scores: Daily risk scores (all customers)
            Schema: cif_no, observation_date, score
        labels: Compliance lifecycle data
            Schema: cif_no, isL2, isSAR, alert_generated_date,
                    case_date_open, case_date_close
        kyc: Static customer profile data
            Schema: cif_no, segment, declared_income
        contexts: List of CaseContext for each customer in batch
        params: Graph computation parameters

        # Optional expensive computations - skip to reduce cost
        skip_network: Skip hub/network metrics (connected_customer_count, is_hub).
            Impact: NetworkPosition will have defaults.
        skip_connected_compliance: Skip connected customer compliance metrics.
            Impact: ComplianceConnected will have defaults.

        # Caching
        cache_path: Optional path for caching intermediate results.
        batch_id: Unique identifier for this batch run.
            Example: f"batch_{date.today().isoformat()}_{len(contexts)}"

    Returns:
        Tuple of:
        - Dict[customer_cif_id, Dict[counterparty_name, CounterpartyEntry]]
        - BatchMetrics with computation statistics

    Caching:
        When cache_path and batch_id are provided, intermediate DataFrames
        are saved to parquet files. On subsequent runs with the same batch_id,
        cached steps are loaded instead of recomputed.

        Cache structure:
            {cache_path}/{batch_id}/
                all_customer_txns.parquet
                counterparties.parquet
                core_metrics.parquet
                network.parquet
                ...
    """
    start_time = time.time()

    if not contexts:
        return {}, BatchMetrics()

    metrics = BatchMetrics(
        total_customers=len(contexts),
        skipped_network=skip_network,
        skipped_connected_compliance=skip_connected_compliance,
    )

    # Get all customer IDs
    customer_ids = [ctx.cif_no for ctx in contexts]
    logger.info(f"[Batch] Processing {len(customer_ids)} customers")

    # Compute date bounds across all contexts
    context_df = _compute_context_df(spark, contexts, params)
    
    # Initialize cache if enabled
    cache: Optional[ComputeCache] = None
    if cache_path and batch_id:
        cache = ComputeCache(spark, cache_path, batch_id)
        logger.info(f"[Batch] Caching enabled: {cache.base_path}")
        cached_status = cache.status()
        cached_steps = [s for s, v in cached_status.items() if v]
        if cached_steps:
            logger.info(f"[Batch] Found cached steps: {cached_steps}")

    # Helper to cache or compute with timing
    def _cached(step: str, compute_fn, *args, **kwargs) -> DataFrame:
        step_start = time.time()
        if cache:
            result = cache.get_or_compute(step, compute_fn, *args, **kwargs)
        else:
            result = compute_fn(*args, **kwargs)
        metrics.step_times[step] = time.time() - step_start
        return result

    # ==========================================================================
    # STEP 1: Pre-filter transactions for all customers
    # ==========================================================================
    logger.info("[Batch Step 1/7] Pre-filtering transactions for all customers")

    def _compute_all_customer_txns():
        return (
            transactions
            .join(context_df, on="cif_no", how="inner")
            .filter(F.col("transaction_date").between(
                F.col("lifetime_start"), F.col("review_date")
            ))
        )

    all_customer_txns = _cached("all_customer_txns", _compute_all_customer_txns)
    all_customer_txns = all_customer_txns.cache()
    metrics.transactions_scanned = all_customer_txns.count()
    logger.info(f"[Batch Step 1/7] Found {metrics.transactions_scanned} transactions")

    # ==========================================================================
    # STEP 2: Extract all unique counterparties across all customers
    # ==========================================================================
    logger.info("[Batch Step 2/7] Extracting unique counterparties")

    def _compute_counterparties():
        return (
            all_customer_txns
            .select(
                "cif_no",
                F.col(_CP).alias("counterparty_account"),
                "counterparty_name",
                "counterparty_cif_id"
            )
            .dropDuplicates(["cif_no", "counterparty_account"])
        )

    counterparties_df = _cached("counterparties", _compute_counterparties)
    counterparties_df = counterparties_df.cache()

    # Get unique accounts across ALL customers (for shared network scans)
    unique_accounts_df = counterparties_df.select("counterparty_account").dropDuplicates()
    all_cp_accounts = [r.counterparty_account for r in unique_accounts_df.collect()]
    metrics.unique_counterparties = len(all_cp_accounts)

    # Count counterparties per customer
    cp_counts = counterparties_df.groupBy("cif_no").count().collect()
    metrics.total_counterparties = sum(r["count"] for r in cp_counts)

    # Find shared counterparties
    #TODO this shared cp concept doesnt make sense in the current version, to be deprecated
    shared_counts = (
        counterparties_df
        .groupBy("counterparty_account")
        .agg(F.countDistinct("cif_no").alias("customer_count"))
        .filter(F.col("customer_count") > 1)
        .count()
    )
    metrics.shared_counterparties = shared_counts

    logger.info(
        f"[Batch Step 2/7] Found {metrics.total_counterparties} total counterparties, "
        f"{metrics.unique_counterparties} unique, {metrics.shared_counterparties} shared"
    )

    # ==========================================================================
    # STEP 3: Compute per-customer core metrics (REQUIRED)
    # ==========================================================================
    logger.info("[Batch Step 3/7] Computing core metrics (relationship, windows)")

    def _compute_core():
        return _compute_core_metrics_batch(all_customer_txns, params)

    core_metrics_df = _cached("core_metrics", _compute_core)

    # ==========================================================================
    # STEP 4: Network properties (OPTIONAL - skip to save time)
    # ==========================================================================
    network_df = None
    if not skip_network:
        logger.info("[Batch Step 4/7] Computing network properties")

        def _compute_network():
            return _compute_network_batch(
                transactions, all_cp_accounts, params.hub_threshold
            )

        network_df = _cached("network", _compute_network)
    else:
        logger.info("[Batch Step 4/7] SKIPPED network properties")

    # ==========================================================================
    # STEP 5: Connected compliance (OPTIONAL - skip to save time)
    # ==========================================================================
    compliance_connected_df = None
    if not skip_connected_compliance and labels is not None:
        logger.info("[Batch Step 5/7] Computing connected compliance")

        def _compute_conn_compliance():
            return _compute_compliance_connected_batch(
                transactions, labels, all_cp_accounts, bounds
            )

        compliance_connected_df = _cached("compliance_connected", _compute_conn_compliance)
    else:
        logger.info("[Batch Step 5/7] SKIPPED connected compliance")

    # ==========================================================================
    # STEP 6: Own compliance + Risk scores + KYC (REQUIRED for node logic)
    # ==========================================================================
    logger.info("[Batch Step 6/7] Computing own compliance, risk scores, KYC")

    # Own compliance (internal counterparties)
    compliance_own_df = None
    if labels is not None:
        def _compute_own_compliance():
            return _compute_compliance_own_batch(counterparties_df, labels)

        compliance_own_df = _cached("compliance_own", _compute_own_compliance)

    # Risk scores
    scores_df = None
    if risk_scores is not None:
        def _compute_scores():
            return _compute_risk_scores_batch(
                counterparties_df, all_customer_txns, risk_scores, bounds, params
            )

        scores_df = _cached("scores", _compute_scores)

    # KYC profiles
    kyc_df = None
    if kyc is not None:
        def _compute_kyc():
            return _compute_kyc_batch(counterparties_df, kyc)

        kyc_df = _cached("kyc_profiles", _compute_kyc)

    # ==========================================================================
    # STEP 7: Join and assemble
    # ==========================================================================
    logger.info("[Batch Step 7/7] Joining all metrics and assembling graphs")

    # Start with core metrics
    full_df = core_metrics_df

    # Join optional shared metrics (by counterparty_account only)
    if network_df is not None:
        full_df = full_df.join(network_df, on="counterparty_account", how="left")

    if compliance_connected_df is not None:
        full_df = full_df.join(compliance_connected_df, on="counterparty_account", how="left")

    # Join required per-customer metrics
    join_keys = ["cif_no", "counterparty_account"]

    if compliance_own_df is not None:
        full_df = full_df.join(compliance_own_df, on=join_keys, how="left")

    if scores_df is not None:
        full_df = full_df.join(scores_df, on=join_keys, how="left")

    if kyc_df is not None:
        full_df = full_df.join(kyc_df, on=join_keys, how="left")

    # Build context lookup and assemble
    context_lookup = {ctx.customer_cif_id: ctx for ctx in contexts}
    results = _assemble_graphs_batch(full_df, context_lookup, params)

    # Cleanup cached DataFrames
    all_customer_txns.unpersist()
    counterparties_df.unpersist()

    metrics.compute_time_seconds = time.time() - start_time
    logger.info(
        f"[Batch Complete] Built graphs for {len(results)} customers "
        f"in {metrics.compute_time_seconds:.1f}s"
    )

    return results, metrics


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _compute_context_df(
    spark: SparkSession,
    contexts: List[CaseContext],
    params: GraphParameters
) -> DataFrame:
    """Compute date bounds across all contexts."""
    # Use: review_date and max review period for each cif 
    # Build context broadcast for per-customer date filtering
    context_data = [
        ctx.model_dump() for ctx in contexts
    ]
    context_schema = (
        "cif_no STRING, event_start DATE, event_end DATE, "
        "baseline_start DATE, baseline_end DATE, review_date DATE"
    )

    context_df = spark.createDataFrame(context_data, context_schema)
    context_df = (context_df
            .withColumn("lifetime_start", F.date_sub("review_date", params.lifetime_lookback_months*30))          
            .withColumn("network_start", F.date_sub("review_date", params.network_lookback_months*30))          
            .withColumn("rating_start", F.date_sub("review_date", params.network_lookback_months*30))          
        )

    return context_df


def _compute_core_metrics_batch(
    all_customer_txns: DataFrame,
    params: GraphParameters,
) -> DataFrame:
    """
    Compute core metrics for all customers in batch.

    Returns DataFrame with:
    - cif_no, counterparty_account, counterparty_name, counterparty_cif_id
    - Relationship: first_txn_date, last_txn_date, months_active, is_bidirectional, is_new_in_event_period
    - Lifetime: lt_in_count, lt_in_amt, lt_out_count, lt_out_amt, lt_net
    - Event: ev_in_count, ev_in_amt, ev_out_count, ev_out_amt, ev_round_count
    - Baseline: bl_in_count, bl_in_amt, bl_out_count, bl_out_amt
    - Comparison: evb_in_change, evb_out_change, evb_is_spike, evb_is_new
    """

    # Relationship profile
    relationship_df = (
        all_customer_txns
        .groupBy("cif_no", _CP, "counterparty_name", "counterparty_cif_id")
        .agg(
            F.min("transaction_date").alias("first_txn_date"),
            F.max("transaction_date").alias("last_txn_date"),
            F.countDistinct(F.date_format("transaction_date", "yyyy-MM")).alias("months_active"),
            F.max(F.when(F.col("direction") == "credit", 1).otherwise(0)).alias("_has_cr"),
            F.max(F.when(F.col("direction") == "debit", 1).otherwise(0)).alias("_has_dr"),
            F.first("event_start").alias("event_start"),
            F.first("event_end").alias("event_end"),
            F.first("baseline_start").alias("baseline_start"),
            F.first("baseline_end").alias("baseline_end"),
        )
        .withColumn("is_bidirectional", (F.col("_has_cr") == 1) & (F.col("_has_dr") == 1))
        .withColumn("is_new_in_event_period", F.col("first_txn_date") >= F.col("event_start"))
        .drop("_has_cr", "_has_dr")
    )

    # Lifetime aggregates
    lifetime_df = (
        all_customer_txns
        .groupBy("cif_no", _CP)
        .agg(
            F.sum(F.when(F.col("direction") == "credit", F.col("amount")).otherwise(0)).alias("lt_in_amt"),
            F.count(F.when(F.col("direction") == "credit", 1)).alias("lt_in_count"),
            F.sum(F.when(F.col("direction") == "debit", F.col("amount")).otherwise(0)).alias("lt_out_amt"),
            F.count(F.when(F.col("direction") == "debit", 1)).alias("lt_out_count"),
        )
        .withColumn("lt_net", F.col("lt_in_amt") - F.col("lt_out_amt"))
    )

    # Event period aggregates
    event_df = (
        all_customer_txns
        .filter(
            (F.col("transaction_date") >= F.col("event_start")) &
            (F.col("transaction_date") <= F.col("event_end"))
        )
        .groupBy("cif_no", _CP)
        .agg(
            F.sum(F.when(F.col("direction") == "credit", F.col("amount")).otherwise(0)).alias("ev_in_amt"),
            F.count(F.when(F.col("direction") == "credit", 1)).alias("ev_in_count"),
            F.sum(F.when(F.col("direction") == "debit", F.col("amount")).otherwise(0)).alias("ev_out_amt"),
            F.count(F.when(F.col("direction") == "debit", 1)).alias("ev_out_count"),
            F.sum(F.when(F.col("amount") % params.round_amount_modulo == 0, 1).otherwise(0)).alias("ev_round_count"),
        )
    )

    # Baseline period aggregates
    baseline_df = (
        all_customer_txns
        .filter(
            (F.col("transaction_date") >= F.col("baseline_start")) &
            (F.col("transaction_date") <= F.col("baseline_end"))
        )
        .groupBy("cif_no", _CP)
        .agg(
            F.sum(F.when(F.col("direction") == "credit", F.col("amount")).otherwise(0)).alias("bl_in_amt"),
            F.count(F.when(F.col("direction") == "credit", 1)).alias("bl_in_count"),
            F.sum(F.when(F.col("direction") == "debit", F.col("amount")).otherwise(0)).alias("bl_out_amt"),
            F.count(F.when(F.col("direction") == "debit", 1)).alias("bl_out_count"),
        )
    )

    # Join all
    result = relationship_df.join(lifetime_df, on=["cif_no", _CP], how="left")
    result = result.join(event_df, on=["cif_no", _CP], how="left")
    result = result.join(baseline_df, on=["cif_no", _CP], how="left")

    # Compute event vs baseline
    result = (
        result
        .withColumn(
            "evb_in_change",
            F.when(
                F.col("bl_in_amt") > 0,
                ((F.col("ev_in_amt") - F.col("bl_in_amt")) / F.col("bl_in_amt")) * 100
            ).otherwise(None)
        )
        .withColumn(
            "evb_out_change",
            F.when(
                F.col("bl_out_amt") > 0,
                ((F.col("ev_out_amt") - F.col("bl_out_amt")) / F.col("bl_out_amt")) * 100
            ).otherwise(None)
        )
        .withColumn(
            "evb_is_spike",
            (F.coalesce(F.col("ev_in_amt"), F.lit(0)) >
             F.coalesce(F.col("bl_in_amt"), F.lit(0)) * params.volume_spike_threshold) |
            (F.coalesce(F.col("ev_out_amt"), F.lit(0)) >
             F.coalesce(F.col("bl_out_amt"), F.lit(0)) * params.volume_spike_threshold)
        )
        .withColumn(
            "evb_is_new",
            F.col("bl_in_amt").isNull() & F.col("bl_out_amt").isNull()
        )
    )

    return result.withColumnRenamed(_CP, "counterparty_account")


def _compute_network_batch(
    all_transactions: DataFrame,
    cp_accounts: List[str],
    hub_threshold: int,
    context_df: DataFrame,
) -> DataFrame:
    """Compute network properties for all counterparties in batch."""
    connected = (
        all_transactions
        .filter(F.col(_CP).isin(cp_accounts))
        #TODO using overall bounds here doesnt make sense. bounds should be with fixed lookback 
        .filter(F.col("transaction_date").between(
            bounds["network_start"], bounds["max_review_date"]
        ))
        .select(_CP, "cif_no")
        .dropDuplicates()
    )

    network = (
        connected
        .groupBy(_CP)
        .agg(F.countDistinct("cif_no").alias("net_cust_count"))
        .withColumn("net_is_hub", F.col("net_cust_count") >= hub_threshold)
        .withColumn(
            "net_hub_score",
            F.when(F.col("net_cust_count") >= hub_threshold,
                   F.col("net_cust_count") / hub_threshold).otherwise(0.0)
        )
    )

    return network.withColumnRenamed(_CP, "counterparty_account")


def _compute_compliance_connected_batch(
    all_transactions: DataFrame,
    labels: DataFrame,
    cp_accounts: List[str],
    bounds: Dict[str, date],
) -> DataFrame:
    """Compute connected compliance metrics for all counterparties in batch."""
    connected = (
        all_transactions
        .filter(F.col(_CP).isin(cp_accounts))
        .filter(F.col("transaction_date").between(
            bounds["network_start"], bounds["max_review_date"]
        ))
        .select(_CP, "cif_no")
        .dropDuplicates()
    )

    is_open_case = F.col("isL2") & F.col("case_date_close").isNull()
    has_alert = F.col("alert_generated_date").isNotNull()

    conn_with_labels = connected.join(F.broadcast(labels), on="cif_no", how="left")

    compliance = (
        conn_with_labels
        .groupBy(_CP)
        .agg(
            F.countDistinct(F.when(has_alert, F.col("cif_no"))).alias("cm_conn_alert"),
            F.countDistinct(F.when(F.col("isL2"), F.col("cif_no"))).alias("cm_conn_case"),
            F.countDistinct(F.when(F.col("isSAR"), F.col("cif_no"))).alias("cm_conn_sar"),
            F.countDistinct(F.when(is_open_case, F.col("cif_no"))).alias("cm_conn_open"),
        )
    )

    return compliance.withColumnRenamed(_CP, "counterparty_account")


def _compute_compliance_own_batch(
    counterparties_df: DataFrame,
    labels: DataFrame,
) -> DataFrame:
    """Compute own compliance metrics for internal counterparties."""
    internal = counterparties_df.filter(F.col("counterparty_cif_id").isNotNull())

    if internal.count() == 0:
        return None

    is_cleared = (
        F.col("isL2") &
        ~F.col("isSAR") &
        F.col("case_date_close").isNotNull()
    )

    own = (
        internal
        .join(F.broadcast(labels), internal.counterparty_cif_id == labels.cif_no, how="left")
        .groupBy(internal.cif_no, "counterparty_account")
        .agg(
            F.count(labels.cif_no).alias("cm_own_alert"),
            F.sum(F.when(F.col("isL2"), 1).otherwise(0)).alias("cm_own_case"),
            F.sum(F.when(F.col("isSAR"), 1).otherwise(0)).alias("cm_own_sar"),
            F.sum(F.when(is_cleared, 1).otherwise(0)).alias("cm_own_clearance"),
            F.max(F.when(is_cleared, F.col("case_date_close"))).alias("cm_own_last_clear"),
        )
    )

    return own


def _compute_risk_scores_batch(
    counterparties_df: DataFrame,
    all_customer_txns: DataFrame,
    risk_scores: DataFrame,
    bounds: Dict[str, date],
    params: GraphParameters,
) -> DataFrame:
    """
    Compute risk scores for counterparties.

    For ALL counterparties:
    - weighted_avg_score: Volume-weighted average risk score of customers
      who transact with this counterparty. Represents "neighborhood risk".

    For INTERNAL counterparties only (have counterparty_cif_id):
    - internal_max_score: Direct risk score lookup
    - internal_risk_rating: Derived rating (high/medium/low)

    Usage pattern:
    - Use internal_max_score when available (internal counterparties)
    - Fall back to weighted_avg_score when internal_max_score is null (external)
    """
    # Max scores for all customers in lookback window
    max_scores = (
        risk_scores
        .filter(F.col("observation_date").between(
            bounds["rating_start"], bounds["max_review_date"]
        ))
        .groupBy("cif_no")
        .agg(F.max("score").alias("_max_score"))
    )

    # =========================================================================
    # STEP 1: Compute weighted_avg_score for ALL counterparties
    # This represents "neighborhood risk" - how risky are the customers
    # who transact with this counterparty
    # =========================================================================
    all_cp_accounts = [
        r.counterparty_account
        for r in counterparties_df.select("counterparty_account").distinct().collect()
    ]

    vol_start = bounds["max_review_date"] - relativedelta(months=params.weighted_score_volume_window)

    # Get transaction volumes per counterparty per transacting customer
    cp_volumes = (
        all_customer_txns
        .filter(F.col(_CP).isin(all_cp_accounts))
        .filter(F.col("transaction_date") >= vol_start)
        .groupBy("cif_no", _CP)
        .agg(F.sum("amount").alias("_vol"))
    )

    # Compute volume-weighted average score per counterparty
    weighted_scores = (
        cp_volumes
        .join(max_scores, on="cif_no", how="left")
        .filter(F.col("_max_score").isNotNull())
        .groupBy(_CP)
        .agg(
            (F.sum(F.col("_max_score") * F.col("_vol")) / F.sum("_vol")).alias("sc_weighted_avg")
        )
        .withColumnRenamed(_CP, "counterparty_account")
    )

    # =========================================================================
    # STEP 2: For internal counterparties, also get direct score lookup
    # =========================================================================
    internal = counterparties_df.filter(F.col("counterparty_cif_id").isNotNull())

    internal_scores = None
    if internal.count() > 0:
        internal_scores = (
            internal
            .join(max_scores, internal.counterparty_cif_id == max_scores.cif_no, how="left")
            .select(
                internal.cif_no,
                "counterparty_account",
                F.col("_max_score").alias("sc_internal_max"),
            )
            .withColumn(
                "sc_internal_rating",
                F.when(F.col("sc_internal_max") >= params.rating_high_threshold, "high")
                .when(F.col("sc_internal_max") >= params.rating_medium_threshold, "medium")
                .otherwise("low")
            )
        )

    # =========================================================================
    # STEP 3: Join weighted scores to all counterparties, then add internal scores
    # =========================================================================
    # Start with all counterparties and their weighted scores
    result = (
        counterparties_df
        .select("cif_no", "counterparty_account")
        .join(weighted_scores, on="counterparty_account", how="left")
    )

    # Add internal scores if available
    if internal_scores is not None:
        result = result.join(
            internal_scores.select("cif_no", "counterparty_account", "sc_internal_max", "sc_internal_rating"),
            on=["cif_no", "counterparty_account"],
            how="left"
        )
    else:
        result = (
            result
            .withColumn("sc_internal_max", F.lit(None))
            .withColumn("sc_internal_rating", F.lit(None))
        )

    return result


def _compute_kyc_batch(
    counterparties_df: DataFrame,
    kyc: DataFrame,
) -> DataFrame:
    """Get KYC profile for internal counterparties."""
    internal = counterparties_df.filter(F.col("counterparty_cif_id").isNotNull())

    if internal.count() == 0:
        return None

    return (
        internal
        .join(F.broadcast(kyc), internal.counterparty_cif_id == kyc.cif_no, how="left")
        .select(
            internal.cif_no,
            "counterparty_account",
            F.col("segment").alias("kyc_segment"),
            F.col("declared_income").alias("kyc_declared_income"),
        )
    )


def _assemble_graphs_batch(
    full_df: DataFrame,
    context_lookup: Dict[str, CaseContext],
    params: GraphParameters,
) -> Dict[str, Dict[str, CounterpartyEntry]]:
    """Assemble CounterpartyEntry objects from the joined DataFrame."""
    results: Dict[str, Dict[str, CounterpartyEntry]] = {}
    rows = full_df.collect()
    skipped = 0

    for row in rows:
        r = {k: v for k, v in row.asDict().items() if v is not None}

        cif_no = r.get("cif_no")
        cp_name = r.get("counterparty_name")
        cp_account = r.get("counterparty_account")

        if not cif_no or not cp_name or not cp_account:
            skipped += 1
            continue

        if cif_no not in results:
            results[cif_no] = {}

        is_internal = r.get("counterparty_cif_id") is not None

        # Helpers
        def _int(val): return int(val) if val is not None else 0
        def _float(val): return round(float(val), 2) if val is not None else 0.0
        def _float_or_none(val): return round(float(val), 4) if val is not None else None
        def _date_str(val):
            if val is None: return None
            return val.isoformat() if isinstance(val, date) else str(val)

        # Build models
        relationship = RelationshipProfile(
            first_transaction_date=_date_str(r.get("first_txn_date")),
            last_transaction_date=_date_str(r.get("last_txn_date")),
            relationship_duration_months=_int(r.get("months_active")),
            months_active=_int(r.get("months_active")),
            is_new_in_event_period=bool(r.get("is_new_in_event_period")),
            is_bidirectional=bool(r.get("is_bidirectional")),
            activity_consistency=ActivityConsistency.NEW,
        )

        lifetime_summary = LifetimeSummary(
            total_inbound_count=_int(r.get("lt_in_count")),
            total_inbound_amount=_float(r.get("lt_in_amt")),
            total_outbound_count=_int(r.get("lt_out_count")),
            total_outbound_amount=_float(r.get("lt_out_amt")),
            net_flow=_float(r.get("lt_net")),
        )

        event_period = EventPeriodAggregates(
            inbound_count=_int(r.get("ev_in_count")),
            inbound_amount=_float(r.get("ev_in_amt")),
            outbound_count=_int(r.get("ev_out_count")),
            outbound_amount=_float(r.get("ev_out_amt")),
            round_amount_count=_int(r.get("ev_round_count")),
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
            own_case_count=_int(r.get("cm_own_case")),
            own_sar_count=_int(r.get("cm_own_sar")),
            own_prior_clearance_count=_int(r.get("cm_own_clearance")),
            own_last_clearance_date=_date_str(r.get("cm_own_last_clear")),
        )

        compliance_connected = ComplianceConnected(
            connected_alert_customer_count=_int(r.get("cm_conn_alert")),
            connected_case_customer_count=_int(r.get("cm_conn_case")),
            connected_sar_customer_count=_int(r.get("cm_conn_sar")),
            connected_case_open_count=_int(r.get("cm_conn_open")),
        )

        internal_profile = None
        external_profile = None

        if is_internal:
            internal_profile = InternalProfile(
                internal_customer_id=r.get("counterparty_cif_id"),
                internal_max_score=_float_or_none(r.get("sc_internal_max")),
                internal_risk_rating=r.get("sc_internal_rating"),
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
            counterparty_account=cp_account,
            counterparty_name=cp_name,
            relationship=relationship,
            lifetime_summary=lifetime_summary,
            event_period=event_period,
            baseline_period=baseline_period,
            event_vs_baseline=event_vs_baseline,
            counterparty_profile=profile,
        )

        results[cif_no][cp_name] = entry

    if skipped > 0:
        logger.warning(f"Skipped {skipped} rows due to missing name/account")

    return results


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    "BatchMetrics",
    "build_counterparty_graphs_batch",
]
