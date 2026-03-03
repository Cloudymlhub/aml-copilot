"""
Graph-first Counterparty Graph — PySpark Implementation

Computes counterparty graphs for a batch of AML cases in one pass.
Identity resolution via account_master, per-customer date windows,
two-pass edge table for 2nd-degree network analysis.

Usage:
    graph = CounterpartyGraph(
        spark, transactions, account_master, contexts,
        risk_scores=risk_scores, labels=labels, kyc=kyc,
    )
    customer = graph.get_customer("CIF-001")
    graph.visualize(customer_cif="CIF-001", output_path="cif001.html")
    graph.save("/data/graphs/batch_2024_03")
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime
from typing import Dict, List, Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DoubleType,
    StringType,
    StructField,
    StructType,
)

from .models import (
    BaselinePeriodAggregates,
    BatchMetrics,
    CaseContext,
    ComplianceConnected,
    ComplianceOwn,
    CounterpartyEntry,
    CustomerGraph,
    CustomerProfile,
    CustomerSummary,
    EventPeriodAggregates,
    EventVsBaseline,
    ExternalProfile,
    GraphParameters,
    InternalProfile,
    LifetimeSummary,
    NetworkPosition,
    RelationshipProfile,
)

logger = logging.getLogger(__name__)


class CounterpartyGraph:
    """
    Counterparty network graph for AML case review.

    Computes counterparty graphs for a batch of cases in one pass.
    Results are immediately available via get_customer().
    """

    def __init__(
        self,
        spark: SparkSession,
        transactions: DataFrame,
        account_master: DataFrame,
        contexts: List[CaseContext],
        params: GraphParameters = GraphParameters(),
        risk_scores: Optional[DataFrame] = None,
        labels: Optional[DataFrame] = None,
        kyc: Optional[DataFrame] = None,
        skip_network: bool = False,
        skip_connected_compliance: bool = False,
        cache_path: Optional[str] = None,
        batch_id: Optional[str] = None,
        overwrite_cache: bool = False,
    ):
        self._spark = spark
        self._params = params
        self.edges: Optional[DataFrame] = None
        self.nodes: Optional[DataFrame] = None
        self._results: Dict[str, CustomerGraph] = {}
        self._metrics = BatchMetrics(
            total_customers=len(contexts),
            skipped_network=skip_network,
            skipped_connected_compliance=skip_connected_compliance,
        )

        if not contexts:
            logger.info("[CounterpartyGraph] No contexts provided, returning empty results")
            return

        # Initialize cache if enabled
        cache = None
        if cache_path and batch_id:
            cache = _ComputeCache(spark, cache_path, batch_id, overwrite_cache)
            cached_steps = cache.cached_steps()
            if cached_steps:
                logger.info(f"[CounterpartyGraph] Cache hit: {cached_steps}")
            else:
                logger.info(f"[CounterpartyGraph] Cache enabled at {cache.base_path} (no cached steps)")

        cif_list = [ctx.cif_no for ctx in contexts]
        logger.info(
            f"[CounterpartyGraph] Starting batch computation for {len(contexts)} customers: "
            f"{cif_list[:5]}{'...' if len(cif_list) > 5 else ''}"
        )
        logger.info(
            f"[CounterpartyGraph] Params: lifetime={params.lifetime_lookback_months}mo, "
            f"network={params.network_lookback_months}mo, hub_threshold={params.hub_threshold}, "
            f"skip_network={skip_network}, skip_compliance={skip_connected_compliance}"
        )
        start_time = time.time()

        # Step 1: Compute per-customer date bounds
        step_start = time.time()
        context_df = _compute_context_df(spark, contexts, params)
        self._metrics.step_times["context_df"] = time.time() - step_start
        logger.info(f"[Step 1/6] Context date bounds computed ({self._metrics.step_times['context_df']:.2f}s)")

        # Step 2: Build edge table (two-pass identity resolution)
        step_start = time.time()
        if cache:
            self.edges = cache.get_or_compute(
                "edge_table",
                lambda: _build_edge_table(transactions, account_master, context_df),
            )
        else:
            self.edges = _build_edge_table(
                transactions, account_master, context_df
            )
        self.edges = self.edges.cache()
        self._metrics.transactions_scanned = self.edges.count()
        self._metrics.step_times["edge_table"] = time.time() - step_start

        internal_edge_count = self.edges.filter(F.col("target_is_internal")).count()
        self_transfer_count = self.edges.filter(F.col("is_self_transfer")).count()
        logger.info(
            f"[Step 2/6] Edge table built ({self._metrics.step_times['edge_table']:.2f}s): "
            f"{self._metrics.transactions_scanned} edges, "
            f"{internal_edge_count} internal, {self_transfer_count} self-transfers"
        )

        # Step 3: Build node attributes
        step_start = time.time()
        source_cifs = {r[0] for r in self.edges.select("source").distinct().collect()}
        internal_targets = {
            r[0]
            for r in self.edges.filter(F.col("target_is_internal"))
            .select("target")
            .distinct()
            .collect()
        }
        edge_cifs = source_cifs | internal_targets

        if cache:
            self.nodes = cache.get_or_compute(
                "node_attrs",
                lambda: _build_node_attributes(spark, labels, kyc, edge_cifs),
            )
        else:
            self.nodes = _build_node_attributes(spark, labels, kyc, edge_cifs)
        self._metrics.step_times["node_attrs"] = time.time() - step_start
        logger.info(
            f"[Step 3/6] Node attributes built ({self._metrics.step_times['node_attrs']:.2f}s): "
            f"{len(edge_cifs)} nodes ({len(source_cifs)} sources, {len(internal_targets)} internal targets), "
            f"labels={'yes' if labels is not None else 'no'}, kyc={'yes' if kyc is not None else 'no'}"
        )

        # Step 4: Compute 1st-degree metrics
        step_start = time.time()
        customer_cifs = {ctx.cif_no for ctx in contexts}
        if cache:
            first_degree_df = cache.get_or_compute(
                "first_degree",
                lambda: _compute_first_degree(self.edges, context_df, params, customer_cifs),
            )
        else:
            first_degree_df = _compute_first_degree(
                self.edges, context_df, params, customer_cifs
            )
        first_degree_count = first_degree_df.count()
        self._metrics.step_times["first_degree"] = time.time() - step_start
        logger.info(
            f"[Step 4/6] First-degree metrics computed ({self._metrics.step_times['first_degree']:.2f}s): "
            f"{first_degree_count} customer-counterparty pairs"
        )

        # Step 5: Compute 2nd-degree metrics
        step_start = time.time()
        if cache:
            second_degree_df = cache.get_or_compute(
                "second_degree",
                lambda: _compute_second_degree(
                    self.edges, self.nodes, first_degree_df, context_df,
                    risk_scores, params, skip_network, skip_connected_compliance,
                ),
            )
        else:
            second_degree_df = _compute_second_degree(
                self.edges,
                self.nodes,
                first_degree_df,
                context_df,
                risk_scores,
                params,
                skip_network,
                skip_connected_compliance,
            )
        self._metrics.step_times["second_degree"] = time.time() - step_start
        logger.info(
            f"[Step 5/6] Second-degree metrics computed ({self._metrics.step_times['second_degree']:.2f}s): "
            f"network={'computed' if not skip_network else 'SKIPPED'}, "
            f"compliance={'computed' if not skip_connected_compliance else 'SKIPPED'}, "
            f"risk_scores={'computed' if risk_scores is not None else 'no data'}"
        )

        # Step 6: Assemble results
        step_start = time.time()
        self._results = _assemble(
            first_degree_df, second_degree_df, self.nodes, contexts, params
        )
        self._metrics.step_times["assemble"] = time.time() - step_start

        # Count counterparties
        total_cps = sum(len(cg.counterparties) for cg in self._results.values())
        all_targets = set()
        hub_total = 0
        high_risk_total = 0
        for cg in self._results.values():
            all_targets.update(cg.counterparties.keys())
            hub_total += cg.summary.hub_counterparties
            high_risk_total += cg.summary.high_risk_counterparties
        self._metrics.total_counterparties = total_cps
        self._metrics.unique_counterparties = len(all_targets)

        self._metrics.compute_time_seconds = time.time() - start_time

        logger.info(
            f"[Step 6/6] Results assembled ({self._metrics.step_times['assemble']:.2f}s): "
            f"{len(self._results)} customers, {total_cps} total counterparties "
            f"({len(all_targets)} unique)"
        )
        logger.info(
            f"[CounterpartyGraph] DONE in {self._metrics.compute_time_seconds:.1f}s — "
            f"hubs={hub_total}, high_risk={high_risk_total}"
        )
        for cif, cg in self._results.items():
            s = cg.summary
            logger.debug(
                f"  {cif}: {s.total_counterparties} cps "
                f"(int={s.internal_count}, ext={s.external_count}, "
                f"hubs={s.hub_counterparties}, high_risk={s.high_risk_counterparties})"
            )

    # --- Access results ---

    @property
    def results(self) -> Dict[str, CustomerGraph]:
        """All computed results. Keyed by customer cif_no."""
        return self._results

    @property
    def metrics(self) -> BatchMetrics:
        """Computation metrics."""
        return self._metrics

    def get_customer(self, cif_no: str) -> Optional[CustomerGraph]:
        """Get one customer's full computed analysis. Returns None if not found."""
        return self._results.get(cif_no)

    def get_node(self, cif_no: str) -> Optional[dict]:
        """
        Light query on raw graph — inspects edge table + node attributes directly.
        Useful for debugging or exploring the graph.
        """
        if self.edges is None:
            return None

        # Node attributes
        node_attrs = {}
        if self.nodes is not None:
            node_rows = self.nodes.filter(F.col("node_cif") == cif_no).collect()
            if node_rows:
                node_attrs = node_rows[0].asDict()

        # Counterparties (outbound edges from this node)
        cp_rows = (
            self.edges.filter(F.col("source") == cif_no)
            .groupBy("target", "target_name", "target_is_internal")
            .agg(
                F.count("*").alias("txn_count"),
                F.sum("amount").alias("total_amount"),
            )
            .collect()
        )

        counterparties = [
            {
                "target": r["target"],
                "target_name": r["target_name"],
                "is_internal": r["target_is_internal"],
                "txn_count": r["txn_count"],
                "total_amount": float(r["total_amount"]) if r["total_amount"] else 0.0,
            }
            for r in cp_rows
        ]

        return {"node_attrs": node_attrs, "counterparties": counterparties}

    # --- Persistence ---

    def save(self, path: str, overwrite: bool = False) -> None:
        """
        Save everything to disk (parquet + JSON).

        Args:
            path: Directory to save to.
            overwrite: If False (default), raises FileExistsError if path already
                contains results. If True, overwrites existing files.
        """
        results_file = os.path.join(path, "results.json")
        if not overwrite and os.path.exists(results_file):
            raise FileExistsError(
                f"Output already exists at {path}. Use overwrite=True to replace."
            )

        logger.info(f"[CounterpartyGraph] Saving to {path} (overwrite={overwrite})")
        os.makedirs(path, exist_ok=True)

        write_mode = "overwrite" if overwrite else "errorifexists"

        # Results as JSON
        results_dict = {
            cif: cg.model_dump() for cif, cg in self._results.items()
        }
        with open(results_file, "w") as f:
            json.dump(results_dict, f, indent=2, default=str)

        # Edge table
        if self.edges is not None:
            self.edges.write.mode(write_mode).parquet(
                os.path.join(path, "edges.parquet")
            )

        # Node attributes
        if self.nodes is not None:
            self.nodes.write.mode(write_mode).parquet(
                os.path.join(path, "nodes.parquet")
            )

        # Metadata
        metadata = {
            "edge_count": self.edge_count,
            "node_count": self.node_count,
            "timestamp": datetime.now().isoformat(),
            "metrics": self._metrics.to_dict(),
            "params": self._params.model_dump(),
        }
        with open(os.path.join(path, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info(
            f"[CounterpartyGraph] Saved: results.json, edges.parquet, nodes.parquet, metadata.json"
        )

    @classmethod
    def load(cls, spark: SparkSession, path: str) -> CounterpartyGraph:
        """Reload from disk. get_customer() and visualize() work immediately."""
        logger.info(f"[CounterpartyGraph] Loading from {path}")
        instance = cls.__new__(cls)
        instance._spark = spark
        instance._results = {}

        # Load results
        results_path = os.path.join(path, "results.json")
        if os.path.exists(results_path):
            with open(results_path) as f:
                raw = json.load(f)
            instance._results = {
                cif: CustomerGraph.model_validate(data)
                for cif, data in raw.items()
            }

        # Load edges
        edges_path = os.path.join(path, "edges.parquet")
        if os.path.exists(edges_path):
            instance.edges = spark.read.parquet(edges_path)
        else:
            instance.edges = None

        # Load nodes
        nodes_path = os.path.join(path, "nodes.parquet")
        if os.path.exists(nodes_path):
            instance.nodes = spark.read.parquet(nodes_path)
        else:
            instance.nodes = None

        # Load metadata
        metadata_path = os.path.join(path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path) as f:
                meta = json.load(f)
            instance._metrics = BatchMetrics(**meta.get("metrics", {}))
            instance._params = GraphParameters(**meta.get("params", {}))
        else:
            instance._metrics = BatchMetrics()
            instance._params = GraphParameters()

        return instance

    # --- Visualization ---

    def visualize(
        self,
        customer_cif: Optional[str] = None,
        title: str = "Counterparty Network",
        output_path: str = "counterparty_graph.html",
    ) -> str:
        """Render results as interactive HTML. Returns file path."""
        from .viz import visualize as _viz

        return _viz(self._results, customer_cif, title, output_path)

    # --- Graph inspection ---

    @property
    def edge_count(self) -> int:
        if self.edges is None:
            return 0
        return self.edges.count()

    @property
    def node_count(self) -> int:
        if self.nodes is None:
            return 0
        return self.nodes.count()

    @property
    def internal_ratio(self) -> float:
        if self.edges is None or self.edge_count == 0:
            return 0.0
        internal = self.edges.filter(F.col("target_is_internal")).count()
        return internal / self.edge_count


# =============================================================================
# COMPUTE CACHE
# =============================================================================


class _ComputeCache:
    """
    Cache for intermediate DataFrames during computation.

    Saves/loads DataFrames as parquet files under:
        {cache_path}/{batch_id}/{step_name}.parquet

    Usage:
        cache = _ComputeCache(spark, "/data/cache", "batch_2024_03")
        df = cache.get_or_compute("edge_table", lambda: expensive_computation())
    """

    def __init__(
        self,
        spark: SparkSession,
        cache_path: str,
        batch_id: str,
        overwrite: bool = False,
    ):
        self._spark = spark
        self._overwrite = overwrite
        self.base_path = os.path.join(cache_path, batch_id)

    def _step_path(self, step: str) -> str:
        return os.path.join(self.base_path, f"{step}.parquet")

    def has(self, step: str) -> bool:
        return not self._overwrite and os.path.exists(self._step_path(step))

    def cached_steps(self) -> List[str]:
        if not os.path.exists(self.base_path):
            return []
        return [
            f.replace(".parquet", "")
            for f in os.listdir(self.base_path)
            if f.endswith(".parquet")
            and (not self._overwrite)
        ]

    def get_or_compute(
        self,
        step: str,
        compute_fn,
    ) -> Optional[DataFrame]:
        path = self._step_path(step)

        if self.has(step):
            logger.info(f"[Cache] Loading cached '{step}' from {path}")
            return self._spark.read.parquet(path)

        logger.debug(f"[Cache] Computing '{step}' (not cached)")
        result = compute_fn()

        if result is not None:
            os.makedirs(self.base_path, exist_ok=True)
            write_mode = "overwrite" if self._overwrite else "errorifexists"
            result.write.mode(write_mode).parquet(path)
            logger.debug(f"[Cache] Saved '{step}' to {path}")

        return result


# =============================================================================
# INTERNAL FUNCTIONS
# =============================================================================


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
    Identity resolution with two-pass scope filtering.

    Pass 1: reviewed customers' transactions (1st degree scope)
    Pass 2: counterparties' own transactions (2nd degree scope)
    Combine + resolve identities via account_master.
    """
    base_cols = [
        "cif_no",
        "counterparty_bank_account",
        "counterparty_name",
        "transaction_date",
        "direction",
        "amount",
    ]

    # --- Pass 1: Reviewed customers' edges ---
    logger.debug("[edge_table] Pass 1: filtering reviewed customers' transactions")
    customer_edges = (
        transactions.join(context_df, on="cif_no", how="inner").filter(
            F.col("transaction_date").between(
                F.col("lifetime_start"), F.col("review_date")
            )
        )
    ).select(base_cols)

    # Extract counterparty targets
    cp_targets = customer_edges.select("counterparty_bank_account").distinct()

    # Resolve internal counterparty CIFs
    cp_cifs = (
        cp_targets.join(
            account_master,
            cp_targets.counterparty_bank_account == account_master.foracid,
            "inner",
        )
        .select(account_master.cif_no)
        .distinct()
    )
    cp_cif_list = [r[0] for r in cp_cifs.collect()]
    logger.debug(
        f"[edge_table] Pass 1 found {len(cp_cif_list)} internal counterparty CIFs"
    )

    # --- Pass 2: Counterparties' own transactions (2nd degree) ---
    if cp_cif_list:
        # Broad date bounds for efficiency
        bounds_row = context_df.agg(
            F.min("network_start").alias("broad_start"),
            F.max("review_date").alias("broad_end"),
        ).first()
        broad_start = bounds_row["broad_start"]
        broad_end = bounds_row["broad_end"]

        # CPs' own outbound transactions
        cp_own_txns = transactions.filter(
            F.col("cif_no").isin(cp_cif_list)
            & F.col("transaction_date").between(broad_start, broad_end)
        ).select(base_cols)

        # Non-reviewed customers transacting with our CPs (inbound to CPs)
        # Use semi-join to avoid ambiguous column names
        reviewed_cifs = [r[0] for r in context_df.select("cif_no").collect()]
        cp_account_list = [r[0] for r in cp_targets.collect()]
        cp_inbound_txns = (
            transactions.filter(
                F.col("counterparty_bank_account").isin(cp_account_list)
                & ~F.col("cif_no").isin(reviewed_cifs)
                & F.col("transaction_date").between(broad_start, broad_end)
            )
            .select(base_cols)
        )

        all_relevant_txns = (
            customer_edges.unionByName(cp_own_txns)
            .unionByName(cp_inbound_txns)
            .dropDuplicates()
        )
        logger.debug(
            f"[edge_table] Pass 2: {len(cp_account_list)} cp accounts, "
            f"broad window {broad_start} → {broad_end}"
        )
    else:
        all_relevant_txns = customer_edges
        logger.debug("[edge_table] No internal counterparties, skipping pass 2")

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

    cif_list = list(edge_cifs)
    cif_df = spark.createDataFrame([(c,) for c in cif_list], ["node_cif"])

    result = cif_df

    if labels is not None:
        is_open_case = F.col("isL2") & F.col("case_date_close").isNull()
        is_cleared = (
            F.col("isL2") & ~F.col("isSAR") & F.col("case_date_close").isNotNull()
        )
        has_alert = F.col("alert_generated_date").isNotNull()

        label_agg = (
            labels.filter(F.col("cif_no").isin(cif_list))
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
        kyc_sub = kyc.filter(F.col("cif_no").isin(cif_list)).select(
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
    # Filter to reviewed customers' edges + join date bounds
    fd_edges = (
        edges.filter(F.col("source").isin(list(customer_cifs)))
        .join(
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

    # Group key
    gk = ["source", "target", "target_is_internal"]

    # Relationship profile
    relationship_df = fd_edges.groupBy(*gk).agg(
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
    )
    relationship_df = relationship_df.withColumn(
        "is_bidirectional", (F.col("_has_cr") == 1) & (F.col("_has_dr") == 1)
    ).withColumn(
        "is_new_in_event_period", F.col("first_txn_date") >= F.col("event_start")
    ).withColumn(
        "is_self_transfer", F.col("source") == F.col("target")
    ).drop("_has_cr", "_has_dr")

    # Lifetime aggregates
    lifetime_df = fd_edges.groupBy(*gk).agg(
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
    lifetime_df = lifetime_df.withColumn(
        "lt_net", F.col("lt_in_amt") - F.col("lt_out_amt")
    ).withColumn(
        "lt_total_amt", F.col("lt_in_amt") + F.col("lt_out_amt")
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

    # Join all
    result = relationship_df.join(lifetime_df, on=gk, how="left")
    result = result.join(event_df, on=gk, how="left")
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

        all_connections = inbound_filtered.unionByName(outbound_filtered)

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

    return result


def _assemble(
    first_degree_df: DataFrame,
    second_degree_df: DataFrame,
    nodes: Optional[DataFrame],
    contexts: List[CaseContext],
    params: GraphParameters,
) -> Dict[str, CustomerGraph]:
    """Join first + second degree, collect, build output objects."""
    # Join
    joined = first_degree_df.join(
        second_degree_df, on=["cif_no", "target", "target_is_internal"], how="left"
    )

    rows = joined.collect()

    # Build node lookup for customer profiles
    node_lookup = {}
    if nodes is not None:
        for r in nodes.collect():
            d = r.asDict()
            node_lookup[d.get("node_cif")] = d

    # Helpers
    def _int(val):
        return int(val) if val is not None else 0

    def _float(val):
        return round(float(val), 2) if val is not None else 0.0

    def _float_or_none(val):
        return round(float(val), 4) if val is not None else None

    def _date_str(val):
        if val is None:
            return None
        return val.isoformat() if isinstance(val, date) else str(val)

    # Group rows by customer
    customer_rows: Dict[str, list] = {}
    for row in rows:
        r = row.asDict()
        cif = r.get("cif_no")
        if cif:
            customer_rows.setdefault(cif, []).append(r)

    results: Dict[str, CustomerGraph] = {}

    for ctx in contexts:
        cif = ctx.cif_no

        # Customer profile from node attributes
        na = node_lookup.get(cif, {})
        profile = CustomerProfile(
            cif_no=cif,
            segment=na.get("node_segment"),
            declared_income=_float_or_none(na.get("node_declared_income")),
            alert_count=_int(na.get("node_alert_count")),
            case_count=_int(na.get("node_case_count")),
            sar_count=_int(na.get("node_sar_count")),
            has_open_case=bool(na.get("node_has_open_case")),
        )

        counterparties: Dict[str, CounterpartyEntry] = {}
        hub_count = 0
        high_risk_count = 0
        internal_count = 0
        external_count = 0

        for r in customer_rows.get(cif, []):
            target = r.get("target")
            if not target:
                continue

            is_internal = bool(r.get("target_is_internal"))
            if is_internal:
                internal_count += 1
            else:
                external_count += 1

            relationship = RelationshipProfile(
                first_transaction_date=_date_str(r.get("first_txn_date")),
                last_transaction_date=_date_str(r.get("last_txn_date")),
                relationship_duration_months=_int(r.get("months_active")),
                months_active=_int(r.get("months_active")),
                is_new_in_event_period=bool(r.get("is_new_in_event_period")),
                is_bidirectional=bool(r.get("is_bidirectional")),
            )

            lifetime = LifetimeSummary(
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

            baseline = BaselinePeriodAggregates(
                inbound_count=_int(r.get("bl_in_count")),
                inbound_amount=_float(r.get("bl_in_amt")),
                outbound_count=_int(r.get("bl_out_count")),
                outbound_amount=_float(r.get("bl_out_amt")),
            )

            evb = EventVsBaseline(
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

            if bool(r.get("net_is_hub")):
                hub_count += 1

            compliance_own = ComplianceOwn(
                own_alert_count=_int(r.get("cm_own_alert")),
                own_case_count=_int(r.get("cm_own_case")),
                own_sar_count=_int(r.get("cm_own_sar")),
                own_has_open_case=bool(r.get("cm_own_has_open")),
                own_prior_clearance_count=_int(r.get("cm_own_clearance")),
                own_last_clearance_date=_date_str(r.get("cm_own_last_clear")),
            )

            compliance_connected = ComplianceConnected(
                connected_alert_customer_count=_int(r.get("cm_conn_alert")),
                connected_case_customer_count=_int(r.get("cm_conn_case")),
                connected_sar_customer_count=_int(r.get("cm_conn_sar")),
                connected_case_open_count=_int(r.get("cm_conn_open")),
            )

            # Internal vs external profile
            internal_profile = None
            external_profile = None

            if is_internal:
                sc_max = _float_or_none(r.get("sc_internal_max"))
                internal_profile = InternalProfile(
                    internal_customer_id=target,
                    internal_max_score=sc_max,
                    internal_risk_rating=r.get("sc_internal_rating"),
                    internal_segment=r.get("kyc_segment"),
                    internal_declared_income=_float_or_none(
                        r.get("kyc_declared_income")
                    ),
                )
                if sc_max is not None and sc_max >= params.rating_high_threshold:
                    high_risk_count += 1
            else:
                external_profile = ExternalProfile(
                    weighted_avg_score=_float_or_none(
                        r.get("sc_external_weighted_avg")
                    ),
                )

            is_self = bool(r.get("is_self_transfer"))

            entry = CounterpartyEntry(
                counterparty_account=r.get("target_account", target),
                counterparty_name=r.get("target_name", target),
                target_is_internal=is_internal,
                is_self_transfer=is_self,
                relationship=relationship,
                lifetime_summary=lifetime,
                event_periods={"event": event_period},
                baseline_period=baseline,
                event_vs_baselines={"event": evb},
                network=network,
                compliance_own=compliance_own,
                compliance_connected=compliance_connected,
                internal_profile=internal_profile,
                external_profile=external_profile,
            )

            counterparties[target] = entry

        summary = CustomerSummary(
            total_counterparties=len(counterparties),
            internal_count=internal_count,
            external_count=external_count,
            hub_counterparties=hub_count,
            high_risk_counterparties=high_risk_count,
        )

        results[cif] = CustomerGraph(
            profile=profile,
            counterparties=counterparties,
            summary=summary,
        )

    return results
