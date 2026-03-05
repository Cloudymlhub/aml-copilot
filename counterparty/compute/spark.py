"""
Compute functions for counterparty graph construction.

Pure functions that transform DataFrames — no cache or orchestration logic.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DateType,
    DoubleType,
    StringType,
    StructField,
    StructType,
)

from ..models import (
    CaseContext,
    CustomerGraph,
    GraphParameters,
)
from .assemble import _assemble_from_rows

logger = logging.getLogger(__name__)


def _compute_context_df(
    spark: SparkSession,
    contexts: List[CaseContext],
    params: GraphParameters,
) -> DataFrame:
    """Compute per-customer date bounds from contexts + params."""
    rows = []
    for ctx in contexts:
        rd = ctx.review_date

        # Event period defaults
        event_start = ctx.event_start
        event_end = ctx.event_end
        if event_start is None:
            event_start = _add_months(rd, -params.default_event_months)
        if event_end is None:
            event_end = rd

        # Baseline defaults: ends where event starts
        baseline_start = ctx.baseline_start
        baseline_end = ctx.baseline_end
        if baseline_start is None:
            baseline_start = _add_months(
                event_start, -params.default_baseline_months
            )
        if baseline_end is None:
            baseline_end = _add_months(event_start, 0)  # day before event_start

        rows.append(
            (
                ctx.cif_no,
                rd,
                event_start,
                event_end,
                baseline_start,
                baseline_end,
            )
        )

    schema = StructType(
        [
            StructField("cif_no", StringType()),
            StructField("review_date", DateType()),
            StructField("event_start", DateType()),
            StructField("event_end", DateType()),
            StructField("baseline_start", DateType()),
            StructField("baseline_end", DateType()),
        ]
    )
    context_df = spark.createDataFrame(rows, schema)

    # Add computed lookback dates using add_months for accuracy
    context_df = (
        context_df.withColumn(
            "lifetime_start",
            F.add_months("review_date", -params.lifetime_lookback_months),
        )
        .withColumn(
            "network_start",
            F.add_months("review_date", -params.network_lookback_months),
        )
        .withColumn(
            "rating_start",
            F.add_months("review_date", -params.rating_lookback_months),
        )
    )

    return context_df


def _add_months(d: date, months: int) -> date:
    """Add months to a date (Python-side, for context computation)."""
    from dateutil.relativedelta import relativedelta

    return d + relativedelta(months=months)


def _build_edge_table(
    transactions: DataFrame,
    account_master: DataFrame,
    context_df: DataFrame,
) -> DataFrame:
    """
    Identity resolution with two targeted scans (no full-bank cache).

    1. Scan 1: reviewed CIFs only → discover counterparty accounts/CIFs
    2. Scan 2: counterparty CIFs + third-party inbound (scoped)
    3. Union + deduplicate + resolve identities via account_master
    """
    base_cols = [
        "cif_no",
        "counterparty_bank_account",
        "counterparty_name",
        "transaction_date",
        "direction",
        "amount",
    ]

    # --- Date bounds ---
    bounds_row = context_df.agg(
        F.min("lifetime_start").alias("broad_start"),
        F.max("review_date").alias("broad_end"),
        F.min("network_start").alias("network_start"),
    ).first()
    broad_start = bounds_row["broad_start"]
    broad_end = bounds_row["broad_end"]
    network_start = bounds_row["network_start"]

    date_filter = F.col("transaction_date").between(broad_start, broad_end)

    # --- Scan 1: Reviewed customers only (scoped, no full-bank cache) ---
    logger.debug(f"[edge_table] Scan 1: reviewed CIFs, window {broad_start} → {broad_end}")
    customer_edges = (
        transactions.filter(date_filter)
        .join(context_df, on="cif_no", how="inner")
        .filter(
            F.col("transaction_date").between(
                F.col("lifetime_start"), F.col("review_date")
            )
        )
        .select(base_cols)
    )

    # Extract counterparty targets + resolve internal CIFs.
    # These stay as DataFrames — used in broadcast joins below instead of
    # collecting to Python lists for .isin(), which scales poorly when the
    # counterparty set grows (large lists get serialized into the query plan).
    cp_targets = customer_edges.select("counterparty_bank_account").distinct()

    cp_cifs = (
        cp_targets.join(
            account_master,
            cp_targets.counterparty_bank_account == account_master.foracid,
            "inner",
        )
        .select(account_master.cif_no.alias("_cp_cif"))
        .distinct()
    )

    cp_cif_count = cp_cifs.count()
    logger.debug(
        f"[edge_table] Found {cp_cif_count} internal counterparty CIFs"
    )

    # --- Scan 2: Counterparties' transactions (2nd degree, scoped) ---
    if cp_cif_count > 0:
        # (b) CPs' own transactions — targeted scan filtered to cp CIFs
        cp_txn_base = transactions.filter(date_filter)
        cp_own_txns = (
            cp_txn_base.join(
                F.broadcast(cp_cifs),
                cp_txn_base.cif_no == cp_cifs._cp_cif,
                "inner",
            )
            .select(base_cols)
        )

        # (c) Non-reviewed customers transacting with our CPs (inbound to CPs).
        # Narrower window (network_start) since this is only for hub detection.
        all_known_cifs = context_df.select(F.col("cif_no").alias("_known_cif")).unionByName(
            cp_cifs.select(F.col("_cp_cif").alias("_known_cif"))
        ).distinct()

        inbound_base = transactions.filter(
            F.col("transaction_date").between(network_start, broad_end)
        )
        cp_inbound_txns = (
            inbound_base.join(
                F.broadcast(cp_targets),
                inbound_base.counterparty_bank_account == cp_targets.counterparty_bank_account,
                "leftsemi",
            )
            .join(
                F.broadcast(all_known_cifs),
                inbound_base.cif_no == all_known_cifs._known_cif,
                "leftanti",
            )
            .select(base_cols)
        )

        all_relevant_txns = (
            customer_edges.unionByName(cp_own_txns)
            .unionByName(cp_inbound_txns)
            .dropDuplicates()
        )
        cp_account_count = cp_targets.count()
        logger.debug(
            f"[edge_table] {cp_account_count} cp accounts, "
            f"{cp_cif_count} cp CIFs from targeted scans"
        )
    else:
        all_relevant_txns = customer_edges
        logger.debug("[edge_table] No internal counterparties, skipping 2nd degree")

    # --- Resolve identities ---
    acct = account_master.withColumnRenamed("cif_no", "_resolved_cif")

    edges = (
        all_relevant_txns.join(
            acct,
            all_relevant_txns.counterparty_bank_account == acct.foracid,
            "left",
        )
        .select(
            F.col("cif_no").alias("source"),
            F.coalesce(F.col("_resolved_cif"), F.col("counterparty_bank_account")).alias(
                "target"
            ),
            F.col("counterparty_bank_account").alias("target_account"),
            F.col("counterparty_name").alias("target_name"),
            F.col("_resolved_cif").isNotNull().alias("target_is_internal"),
            (F.col("cif_no") == F.coalesce(F.col("_resolved_cif"), F.col("counterparty_bank_account"))).alias(
                "is_self_transfer"
            ),
            "transaction_date",
            "direction",
            "amount",
        )
    )

    return edges


def _build_node_attributes(
    spark: SparkSession,
    labels: Optional[DataFrame],
    kyc: Optional[DataFrame],
    edge_cifs: set,
) -> Optional[DataFrame]:
    """Static per-node attributes. Scoped to CIFs in the edge table."""
    if not edge_cifs:
        return None

    # Build a small broadcast-able DataFrame of CIFs to scope against.
    # Used in broadcast semi-joins below instead of .isin(python_list),
    # which embeds the full list in the query plan and scales poorly.
    cif_df = spark.createDataFrame([(c,) for c in edge_cifs], ["node_cif"])

    result = cif_df

    if labels is not None:
        is_open_case = F.col("isL2") & F.col("case_date_close").isNull()
        is_cleared = (
            F.col("isL2") & ~F.col("isSAR") & F.col("case_date_close").isNotNull()
        )
        has_alert = F.col("alert_generated_date").isNotNull()

        # Broadcast semi-join to scope labels to edge CIFs, then aggregate
        label_agg = (
            labels.join(
                F.broadcast(cif_df),
                labels.cif_no == cif_df.node_cif,
                "leftsemi",
            )
            .groupBy("cif_no")
            .agg(
                F.sum(F.when(has_alert, 1).otherwise(0)).alias("node_alert_count"),
                F.sum(F.when(F.col("isL2"), 1).otherwise(0)).alias("node_case_count"),
                F.sum(F.when(F.col("isSAR"), 1).otherwise(0)).alias("node_sar_count"),
                F.max(F.when(is_open_case, True).otherwise(False)).alias(
                    "node_has_open_case"
                ),
                F.sum(F.when(is_cleared, 1).otherwise(0)).alias(
                    "node_clearance_count"
                ),
                F.max(F.when(is_cleared, F.col("case_date_close"))).alias(
                    "node_last_clearance"
                ),
            )
        )
        result = result.join(
            label_agg, result.node_cif == label_agg.cif_no, "left"
        ).drop(label_agg.cif_no)
    else:
        result = (
            result.withColumn("node_alert_count", F.lit(0))
            .withColumn("node_case_count", F.lit(0))
            .withColumn("node_sar_count", F.lit(0))
            .withColumn("node_has_open_case", F.lit(False))
            .withColumn("node_clearance_count", F.lit(0))
            .withColumn("node_last_clearance", F.lit(None).cast(DateType()))
        )

    if kyc is not None:
        # Broadcast semi-join to scope KYC to edge CIFs
        kyc_sub = kyc.join(
            F.broadcast(cif_df), kyc.cif_no == cif_df.node_cif, "leftsemi"
        ).select(
            F.col("cif_no").alias("_kyc_cif"),
            F.col("segment").alias("node_segment"),
            F.col("declared_income").alias("node_declared_income"),
        )
        result = result.join(
            kyc_sub, result.node_cif == kyc_sub._kyc_cif, "left"
        ).drop("_kyc_cif")
    else:
        result = result.withColumn("node_segment", F.lit(None).cast(StringType()))
        result = result.withColumn(
            "node_declared_income", F.lit(None).cast(DoubleType())
        )

    return result


def _compute_first_degree(
    edges: DataFrame,
    context_df: DataFrame,
    params: GraphParameters,
    customer_cifs: set,
) -> DataFrame:
    """
    1st-degree metrics: filter edges where source is a reviewed customer,
    within that customer's lifetime window.
    """
    # Filter to reviewed customers' edges + join date bounds.
    # The inner join on context_df already restricts to reviewed CIFs,
    # so no separate .isin() filter is needed.
    fd_edges = (
        edges.join(
            context_df,
            edges.source == context_df.cif_no,
            "inner",
        )
        .filter(
            F.col("transaction_date").between(
                F.col("lifetime_start"), F.col("review_date")
            )
        )
    )

    # Group key for all per-counterparty aggregations
    gk = ["source", "target", "target_is_internal"]

    # --- Relationship + Lifetime in one groupBy ---
    # These share the same group key and source (fd_edges), so merging them
    # eliminates a redundant full scan + shuffle of fd_edges.
    rel_lifetime_df = fd_edges.groupBy(*gk).agg(
        # Relationship profile aggs
        F.min("transaction_date").alias("first_txn_date"),
        F.max("transaction_date").alias("last_txn_date"),
        F.countDistinct(F.date_format("transaction_date", "yyyy-MM")).alias(
            "months_active"
        ),
        F.max(F.when(F.col("direction") == "credit", 1).otherwise(0)).alias(
            "_has_cr"
        ),
        F.max(F.when(F.col("direction") == "debit", 1).otherwise(0)).alias(
            "_has_dr"
        ),
        F.first("target_account").alias("target_account"),
        F.first("target_name").alias("target_name"),
        F.first("event_start").alias("event_start"),
        F.first("event_end").alias("event_end"),
        F.first("baseline_start").alias("baseline_start"),
        F.first("baseline_end").alias("baseline_end"),
        F.first("review_date").alias("review_date"),
        # Lifetime aggs (same source data, saves a full rescan)
        F.sum(
            F.when(F.col("direction") == "credit", F.col("amount")).otherwise(0)
        ).alias("lt_in_amt"),
        F.count(F.when(F.col("direction") == "credit", 1)).alias("lt_in_count"),
        F.sum(
            F.when(F.col("direction") == "debit", F.col("amount")).otherwise(0)
        ).alias("lt_out_amt"),
        F.count(F.when(F.col("direction") == "debit", 1)).alias("lt_out_count"),
        F.count("*").alias("lt_total_count"),
    )

    # Derived relationship columns
    rel_lifetime_df = (
        rel_lifetime_df.withColumn(
            "is_bidirectional", (F.col("_has_cr") == 1) & (F.col("_has_dr") == 1)
        )
        .withColumn(
            "is_new_in_event_period", F.col("first_txn_date") >= F.col("event_start")
        )
        .withColumn("is_self_transfer", F.col("source") == F.col("target"))
        .drop("_has_cr", "_has_dr")
        # Derived lifetime columns
        .withColumn("lt_net", F.col("lt_in_amt") - F.col("lt_out_amt"))
        .withColumn("lt_total_amt", F.col("lt_in_amt") + F.col("lt_out_amt"))
    )

    # Event period aggregates
    event_edges = fd_edges.filter(
        F.col("transaction_date").between(
            F.col("event_start"), F.col("event_end")
        )
    )
    event_df = event_edges.groupBy(*gk).agg(
        F.sum(
            F.when(F.col("direction") == "credit", F.col("amount")).otherwise(0)
        ).alias("ev_in_amt"),
        F.count(F.when(F.col("direction") == "credit", 1)).alias("ev_in_count"),
        F.sum(
            F.when(F.col("direction") == "debit", F.col("amount")).otherwise(0)
        ).alias("ev_out_amt"),
        F.count(F.when(F.col("direction") == "debit", 1)).alias("ev_out_count"),
        F.sum(
            F.when(
                F.col("amount") % params.round_amount_modulo == 0, 1
            ).otherwise(0)
        ).alias("ev_round_count"),
    )

    # Baseline period aggregates
    baseline_edges = fd_edges.filter(
        F.col("transaction_date").between(
            F.col("baseline_start"), F.col("baseline_end")
        )
    )
    baseline_df = baseline_edges.groupBy(*gk).agg(
        F.sum(
            F.when(F.col("direction") == "credit", F.col("amount")).otherwise(0)
        ).alias("bl_in_amt"),
        F.count(F.when(F.col("direction") == "credit", 1)).alias("bl_in_count"),
        F.sum(
            F.when(F.col("direction") == "debit", F.col("amount")).otherwise(0)
        ).alias("bl_out_amt"),
        F.count(F.when(F.col("direction") == "debit", 1)).alias("bl_out_count"),
    )

    # Join all — rel_lifetime_df is the base since it covers all counterparties;
    # event/baseline are left-joined (a cp may have no txns in those periods).
    result = rel_lifetime_df.join(event_df, on=gk, how="left")
    result = result.join(baseline_df, on=gk, how="left")

    # Fill nulls for event/baseline (no transactions in that period)
    for col_name in [
        "ev_in_amt", "ev_in_count", "ev_out_amt", "ev_out_count", "ev_round_count",
        "bl_in_amt", "bl_in_count", "bl_out_amt", "bl_out_count",
    ]:
        result = result.withColumn(col_name, F.coalesce(F.col(col_name), F.lit(0)))

    # Event vs baseline comparison
    result = (
        result.withColumn(
            "evb_in_change",
            F.when(
                F.col("bl_in_amt") > 0,
                ((F.col("ev_in_amt") - F.col("bl_in_amt")) / F.col("bl_in_amt"))
                * 100,
            ).otherwise(None),
        )
        .withColumn(
            "evb_out_change",
            F.when(
                F.col("bl_out_amt") > 0,
                (
                    (F.col("ev_out_amt") - F.col("bl_out_amt"))
                    / F.col("bl_out_amt")
                )
                * 100,
            ).otherwise(None),
        )
        .withColumn(
            "evb_is_spike",
            (
                F.col("ev_in_amt")
                > F.col("bl_in_amt") * params.volume_spike_threshold
            )
            | (
                F.col("ev_out_amt")
                > F.col("bl_out_amt") * params.volume_spike_threshold
            ),
        )
        .withColumn(
            "evb_is_new",
            (F.col("bl_in_count") == 0) & (F.col("bl_out_count") == 0),
        )
    )

    # Rename source to cif_no for consistency
    result = result.withColumnRenamed("source", "cif_no")

    return result


def _compute_second_degree(
    edges: DataFrame,
    nodes: Optional[DataFrame],
    first_degree_df: DataFrame,
    context_df: DataFrame,
    risk_scores: Optional[DataFrame],
    params: GraphParameters,
    skip_network: bool,
    skip_connected_compliance: bool,
) -> DataFrame:
    """
    2nd-degree metrics: network (hub detection), connected compliance, risk scores.
    """
    # Get counterparty list with per-customer date bounds
    cp_list = (
        first_degree_df.select("cif_no", "target", "target_is_internal")
        .distinct()
        .join(
            context_df.select("cif_no", "network_start", "review_date", "rating_start"),
            on="cif_no",
        )
    )

    result = cp_list.select("cif_no", "target", "target_is_internal")
    internal_cp_count = cp_list.filter(F.col("target_is_internal")).select("target").distinct().count()
    logger.debug(
        f"[second_degree] {internal_cp_count} internal counterparties eligible for outbound expansion"
    )

    # --- Network (hub detection) ---
    if not skip_network:
        # INBOUND: others transacting with this cp
        inbound = edges.select(
            F.col("target").alias("cp_id"),
            F.col("source").alias("connected_node"),
            "transaction_date",
        )

        # OUTBOUND: cp's own transactions (internal only)
        outbound = edges.select(
            F.col("source").alias("cp_id"),
            F.col("target").alias("connected_node"),
            "transaction_date",
        )

        # Join inbound with cp_list (carrying date bounds)
        inbound_filtered = (
            cp_list.join(inbound, cp_list.target == inbound.cp_id, "inner")
            .filter(
                F.col("transaction_date").between(
                    F.col("network_start"), F.col("review_date")
                )
            )
            .select("cif_no", "target", "connected_node", "transaction_date")
        )

        # Join outbound with cp_list (only internal cps)
        outbound_filtered = (
            cp_list.filter(F.col("target_is_internal"))
            .join(outbound, cp_list.target == outbound.cp_id, "inner")
            .filter(
                F.col("transaction_date").between(
                    F.col("network_start"), F.col("review_date")
                )
            )
            .select("cif_no", "target", "connected_node", "transaction_date")
        )

        # Cache all_connections — it's consumed 3 times (network_df,
        # conn_compliance, neighbor_scores), so caching avoids recomputing
        # the union + filtered joins for each downstream use.
        all_connections = inbound_filtered.unionByName(outbound_filtered).cache()

        # Compute network metrics per (cif_no, target)
        network_df = (
            all_connections.groupBy("cif_no", "target")
            .agg(F.countDistinct("connected_node").alias("net_cust_count"))
            .withColumn(
                "net_is_hub", F.col("net_cust_count") >= params.hub_threshold
            )
            .withColumn(
                "net_hub_score",
                F.when(
                    F.col("net_cust_count") >= params.hub_threshold,
                    F.col("net_cust_count") / F.lit(params.hub_threshold),
                ).otherwise(0.0),
            )
        )

        result = result.join(network_df, on=["cif_no", "target"], how="left")

        # --- Connected compliance ---
        if not skip_connected_compliance and nodes is not None:
            conn_compliance = (
                all_connections.join(
                    nodes,
                    all_connections.connected_node == nodes.node_cif,
                    "left",
                )
                .groupBy("cif_no", "target")
                .agg(
                    F.sum(
                        F.coalesce(F.col("node_alert_count"), F.lit(0))
                    ).alias("cm_conn_alert"),
                    F.sum(
                        F.coalesce(F.col("node_case_count"), F.lit(0))
                    ).alias("cm_conn_case"),
                    F.sum(
                        F.coalesce(F.col("node_sar_count"), F.lit(0))
                    ).alias("cm_conn_sar"),
                    F.sum(
                        F.when(F.col("node_has_open_case"), 1).otherwise(0)
                    ).alias("cm_conn_open"),
                )
            )
            result = result.join(
                conn_compliance, on=["cif_no", "target"], how="left"
            )
    else:
        all_connections = None

    # --- Own compliance (direct node lookup for internal CPs) ---
    # Note: all_connections may still be used below for neighbor_scores,
    # so we defer unpersist until after all downstream consumers are done.
    if nodes is not None:
        own_compliance = nodes.select(
            F.col("node_cif").alias("_oc_target"),
            F.col("node_alert_count").alias("cm_own_alert"),
            F.col("node_case_count").alias("cm_own_case"),
            F.col("node_sar_count").alias("cm_own_sar"),
            F.col("node_has_open_case").alias("cm_own_has_open"),
            F.col("node_clearance_count").alias("cm_own_clearance"),
            F.col("node_last_clearance").alias("cm_own_last_clear"),
            F.col("node_segment").alias("kyc_segment"),
            F.col("node_declared_income").alias("kyc_declared_income"),
        )
        result = result.join(
            own_compliance,
            (result.target == own_compliance._oc_target)
            & (result.target_is_internal),
            "left",
        ).drop("_oc_target")

    # --- Risk scores ---
    if risk_scores is not None:
        # Internal CPs: direct score lookup, date-filtered per customer
        internal_scores = (
            cp_list.filter(F.col("target_is_internal"))
            .join(
                risk_scores,
                (cp_list.target == risk_scores.cif_no)
                & (
                    F.col("observation_date").between(
                        F.col("rating_start"), F.col("review_date")
                    )
                ),
                "inner",
            )
            .groupBy(cp_list.cif_no, "target")
            .agg(F.max("score").alias("sc_internal_max"))
            .withColumn(
                "sc_internal_rating",
                F.when(
                    F.col("sc_internal_max") >= params.rating_high_threshold,
                    "high",
                )
                .when(
                    F.col("sc_internal_max") >= params.rating_medium_threshold,
                    "medium",
                )
                .otherwise("low"),
            )
        )
        result = result.join(
            internal_scores, on=["cif_no", "target"], how="left"
        )

        # External CPs: weighted avg of neighbors' scores
        if all_connections is not None:
            neighbor_scores = (
                all_connections.join(
                    risk_scores.withColumnRenamed("cif_no", "_sc_cif"),
                    (all_connections.connected_node == F.col("_sc_cif")),
                    "inner",
                )
                .join(
                    context_df.select(
                        F.col("cif_no").alias("_ctx_cif"),
                        F.col("rating_start").alias("_rs"),
                        F.col("review_date").alias("_rd"),
                    ),
                    all_connections.cif_no == F.col("_ctx_cif"),
                    "inner",
                )
                .filter(F.col("observation_date").between(F.col("_rs"), F.col("_rd")))
                .groupBy("cif_no", "target")
                .agg(F.avg("score").alias("sc_external_weighted_avg"))
            )
            result = result.join(
                neighbor_scores, on=["cif_no", "target"], how="left"
            )

    # Free cached all_connections now that all downstream consumers are done
    if all_connections is not None:
        all_connections.unpersist()

    return result


def _assemble(
    first_degree_df: DataFrame,
    second_degree_df: DataFrame,
    nodes: Optional[DataFrame],
    contexts: List[CaseContext],
    params: GraphParameters,
) -> Dict[str, CustomerGraph]:
    """Join first + second degree, collect, build output objects."""
    joined = first_degree_df.join(
        second_degree_df, on=["cif_no", "target", "target_is_internal"], how="left"
    )

    rows = [r.asDict() for r in joined.collect()]
    node_rows = [r.asDict() for r in nodes.collect()] if nodes is not None else []

    return _assemble_from_rows(rows, node_rows, contexts, params)
