"""
Graph-first Counterparty Graph — Dual Engine (Spark / Pandas)

Computes counterparty graphs for a batch of AML cases in one pass.
Identity resolution via account_master, per-customer date windows,
single-scan edge table for 2nd-degree network analysis.

Usage:
    # Spark (default)
    graph = create_counterparty_graph(
        spark, transactions, account_master, contexts,
        risk_scores=risk_scores, labels=labels, kyc=kyc,
    )

    # Pandas — requires cache (Spark→parquet→pandas bridge)
    graph = create_counterparty_graph(
        spark, transactions, account_master, contexts,
        engine="pandas", cache_path="/cache", batch_id="run_001",
    )

    customer = graph.get_customer("CIF-001")
    graph.visualize(customer_cif="CIF-001", output_path="cif001.html")
    graph.save("/data/graphs/batch_2024_03")

    # Load from disk
    loaded = load_counterparty_graph(spark, "/data/graphs/batch_2024_03")
"""

from __future__ import annotations

import json
import logging
import os
import time
from abc import abstractmethod
from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .cache import _ComputeCache, _cached, _cached_pandas
from .compute import spark as compute_spark
from .compute import pandas as compute_pd
from .models import (
    BatchMetrics,
    CaseContext,
    CustomerGraph,
    GraphParameters,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Base class — shared state, results access, persistence, visualization
# =============================================================================


class _CounterpartyGraphBase:
    """
    Base for counterparty graph implementations.

    Holds shared state (results, metrics) and provides results access,
    save/load, and visualization. Subclasses own edges/nodes with
    engine-specific types and implement _run().
    """

    def __init__(
        self,
        spark: SparkSession,
        contexts: List[CaseContext],
        params: GraphParameters,
        skip_network: bool,
        skip_connected_compliance: bool,
    ):
        self._spark = spark
        self._params = params
        self._contexts = contexts
        self._skip_network = skip_network
        self._skip_connected_compliance = skip_connected_compliance
        self._results: Dict[str, CustomerGraph] = {}
        self._metrics = BatchMetrics(
            total_customers=len(contexts),
            skipped_network=skip_network,
            skipped_connected_compliance=skip_connected_compliance,
        )

    @abstractmethod
    def _run(
        self,
        transactions,
        account_master,
        risk_scores,
        labels,
        kyc,
        cache,
    ):
        """Execute the 6-step computation pipeline. Called by the factory."""
        ...

    # --- Results access ---

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

    @abstractmethod
    def get_node(self, cif_no: str) -> Optional[dict]:
        """Light query on raw graph."""
        ...

    # --- Graph inspection (abstract) ---

    @property
    @abstractmethod
    def edge_count(self) -> int: ...

    @property
    @abstractmethod
    def node_count(self) -> int: ...

    @property
    @abstractmethod
    def internal_ratio(self) -> float: ...

    # --- Persistence ---

    @abstractmethod
    def _save_edges(self, path: str, overwrite: bool) -> None: ...

    @abstractmethod
    def _save_nodes(self, path: str, overwrite: bool) -> None: ...

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

        # Results as JSON
        results_dict = {
            cif: cg.model_dump() for cif, cg in self._results.items()
        }
        with open(results_file, "w") as f:
            json.dump(results_dict, f, indent=2, default=str)

        # Edge table + Node attributes
        self._save_edges(path, overwrite)
        self._save_nodes(path, overwrite)

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
    def _load_common(cls, spark: SparkSession, path: str) -> _CounterpartyGraphBase:
        """Reload from disk. Returns a SparkCounterpartyGraph (always Spark mode)."""
        logger.info(f"[CounterpartyGraph] Loading from {path}")
        instance = SparkCounterpartyGraph.__new__(SparkCounterpartyGraph)
        instance._spark = spark
        instance._contexts = []
        instance._skip_network = False
        instance._skip_connected_compliance = False
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
        instance.edges = spark.read.parquet(edges_path) if os.path.exists(edges_path) else None

        # Load nodes
        nodes_path = os.path.join(path, "nodes.parquet")
        instance.nodes = spark.read.parquet(nodes_path) if os.path.exists(nodes_path) else None

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

    # --- Shared finalization ---

    def _finalize_metrics(self, start_time: float):
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
            f"[Results] {len(self._results)} customers, {total_cps} total counterparties "
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


# =============================================================================
# Spark implementation
# =============================================================================


class SparkCounterpartyGraph(_CounterpartyGraphBase):
    """PySpark-based counterparty graph. Works at any scale."""

    def __init__(
        self,
        spark: SparkSession,
        contexts: List[CaseContext],
        params: GraphParameters,
        skip_network: bool,
        skip_connected_compliance: bool,
    ):
        super().__init__(spark, contexts, params, skip_network, skip_connected_compliance)
        self.edges: Optional[DataFrame] = None
        self.nodes: Optional[DataFrame] = None

    def _run(
        self,
        transactions: DataFrame,
        account_master: DataFrame,
        risk_scores: Optional[DataFrame],
        labels: Optional[DataFrame],
        kyc: Optional[DataFrame],
        cache: Optional[_ComputeCache],
    ):
        start_time = time.time()
        contexts = self._contexts
        params = self._params
        skip_network = self._skip_network
        skip_connected_compliance = self._skip_connected_compliance

        # Step 1: Context date bounds
        step_start = time.time()
        context_df = compute_spark._compute_context_df(self._spark, contexts, params)
        self._metrics.step_times["context_df"] = time.time() - step_start
        logger.info(f"[Step 1/6] Context date bounds computed ({self._metrics.step_times['context_df']:.2f}s)")

        # Step 2: Edge table
        step_start = time.time()
        self.edges = _cached(
            cache, "edge_table",
            compute_spark._build_edge_table, transactions, account_master, context_df,
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

        # Step 3: Node attributes
        step_start = time.time()
        cif_sets = self.edges.agg(
            F.collect_set("source").alias("sources"),
            F.collect_set(
                F.when(F.col("target_is_internal"), F.col("target"))
            ).alias("internal_targets"),
        ).first()
        source_cifs = set(cif_sets["sources"])
        internal_targets = set(cif_sets["internal_targets"]) - {None}
        edge_cifs = source_cifs | internal_targets

        self.nodes = _cached(
            cache, "node_attrs",
            compute_spark._build_node_attributes, self._spark, labels, kyc, edge_cifs,
        )
        self._metrics.step_times["node_attrs"] = time.time() - step_start
        logger.info(
            f"[Step 3/6] Node attributes built ({self._metrics.step_times['node_attrs']:.2f}s): "
            f"{len(edge_cifs)} nodes ({len(source_cifs)} sources, {len(internal_targets)} internal targets), "
            f"labels={'yes' if labels is not None else 'no'}, kyc={'yes' if kyc is not None else 'no'}"
        )

        # Step 4: First-degree metrics
        step_start = time.time()
        customer_cifs = {ctx.cif_no for ctx in contexts}
        first_degree_df = _cached(
            cache, "first_degree",
            compute_spark._compute_first_degree, self.edges, context_df, params, customer_cifs,
        )
        first_degree_count = first_degree_df.count()
        self._metrics.step_times["first_degree"] = time.time() - step_start
        logger.info(
            f"[Step 4/6] First-degree metrics computed ({self._metrics.step_times['first_degree']:.2f}s): "
            f"{first_degree_count} customer-counterparty pairs"
        )

        # Step 5: Second-degree metrics
        step_start = time.time()
        second_degree_df = _cached(
            cache, "second_degree",
            compute_spark._compute_second_degree,
            self.edges, self.nodes, first_degree_df, context_df,
            risk_scores, params, skip_network, skip_connected_compliance,
        )
        self._metrics.step_times["second_degree"] = time.time() - step_start
        logger.info(
            f"[Step 5/6] Second-degree metrics computed ({self._metrics.step_times['second_degree']:.2f}s): "
            f"network={'computed' if not skip_network else 'SKIPPED'}, "
            f"compliance={'computed' if not skip_connected_compliance else 'SKIPPED'}, "
            f"risk_scores={'computed' if risk_scores is not None else 'no data'}"
        )

        # Step 6: Assemble
        step_start = time.time()
        self._results = compute_spark._assemble(
            first_degree_df, second_degree_df, self.nodes, contexts, params
        )
        self._metrics.step_times["assemble"] = time.time() - step_start

        self._finalize_metrics(start_time)

    # --- Engine-specific properties ---

    @property
    def edge_count(self) -> int:
        return self.edges.count() if self.edges is not None else 0

    @property
    def node_count(self) -> int:
        return self.nodes.count() if self.nodes is not None else 0

    @property
    def internal_ratio(self) -> float:
        if self.edges is None or self.edge_count == 0:
            return 0.0
        return self.edges.filter(F.col("target_is_internal")).count() / self.edge_count

    def get_node(self, cif_no: str) -> Optional[dict]:
        if self.edges is None:
            return None

        node_attrs = {}
        if self.nodes is not None:
            node_rows = self.nodes.filter(F.col("node_cif") == cif_no).collect()
            if node_rows:
                node_attrs = node_rows[0].asDict()

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

    def _save_edges(self, path: str, overwrite: bool) -> None:
        if self.edges is not None:
            mode = "overwrite" if overwrite else "errorifexists"
            self.edges.write.mode(mode).parquet(os.path.join(path, "edges.parquet"))

    def _save_nodes(self, path: str, overwrite: bool) -> None:
        if self.nodes is not None:
            mode = "overwrite" if overwrite else "errorifexists"
            self.nodes.write.mode(mode).parquet(os.path.join(path, "nodes.parquet"))


# =============================================================================
# Pandas implementation
# =============================================================================


class PandasCounterpartyGraph(_CounterpartyGraphBase):
    """
    Pandas-based counterparty graph. Fast for small batches (< 100 CIFs).

    Spark extracts CIF-scoped data to parquet cache, then pandas does all compute.
    """

    def __init__(
        self,
        spark: SparkSession,
        contexts: List[CaseContext],
        params: GraphParameters,
        skip_network: bool,
        skip_connected_compliance: bool,
    ):
        super().__init__(spark, contexts, params, skip_network, skip_connected_compliance)
        self.edges: Optional[pd.DataFrame] = None
        self.nodes: Optional[pd.DataFrame] = None

    def _run(
        self,
        transactions: DataFrame,
        account_master: DataFrame,
        risk_scores: Optional[DataFrame],
        labels: Optional[DataFrame],
        kyc: Optional[DataFrame],
        cache: _ComputeCache,
    ):
        start_time = time.time()
        contexts = self._contexts
        params = self._params
        skip_network = self._skip_network
        skip_connected_compliance = self._skip_connected_compliance

        # Step 1: Context date bounds (pure Python, no Spark)
        step_start = time.time()
        context_df = compute_pd._compute_context_df(contexts, params)
        self._metrics.step_times["context_df"] = time.time() - step_start
        logger.info(f"[Step 1/6] Context date bounds computed ({self._metrics.step_times['context_df']:.2f}s)")

        # Step 2: Extract data via Spark → parquet, then read as pandas
        step_start = time.time()
        self._extract_to_cache(
            cache, transactions, account_master, context_df,
            risk_scores, labels, kyc,
        )
        self._metrics.step_times["extraction"] = time.time() - step_start
        logger.info(f"[Step 2/6] Spark extraction to cache ({self._metrics.step_times['extraction']:.2f}s)")

        # Read extracted data as pandas
        txns_pd = cache.read_pandas("input_txns")
        acct_pd = cache.read_pandas("input_account_master")
        labels_pd = cache.read_pandas("input_labels") if cache.has("input_labels") else None
        kyc_pd = cache.read_pandas("input_kyc") if cache.has("input_kyc") else None
        risk_pd = cache.read_pandas("input_risk_scores") if cache.has("input_risk_scores") else None

        # Step 3: Edge table (pandas)
        step_start = time.time()
        self.edges = _cached_pandas(
            cache, "edge_table",
            compute_pd._build_edge_table, txns_pd, acct_pd, context_df,
        )
        self._metrics.transactions_scanned = len(self.edges)
        self._metrics.step_times["edge_table"] = time.time() - step_start

        internal_edge_count = int(self.edges["target_is_internal"].sum())
        self_transfer_count = int(self.edges["is_self_transfer"].sum())
        logger.info(
            f"[Step 3/6] Edge table built ({self._metrics.step_times['edge_table']:.2f}s): "
            f"{self._metrics.transactions_scanned} edges, "
            f"{internal_edge_count} internal, {self_transfer_count} self-transfers"
        )

        # Step 4: Node attributes (pandas)
        step_start = time.time()
        source_cifs = set(self.edges["source"].unique())
        internal_targets = set(
            self.edges.loc[self.edges["target_is_internal"], "target"].unique()
        )
        edge_cifs = source_cifs | internal_targets

        self.nodes = _cached_pandas(
            cache, "node_attrs",
            compute_pd._build_node_attributes, labels_pd, kyc_pd, edge_cifs,
        )
        self._metrics.step_times["node_attrs"] = time.time() - step_start
        logger.info(
            f"[Step 4/6] Node attributes built ({self._metrics.step_times['node_attrs']:.2f}s): "
            f"{len(edge_cifs)} nodes"
        )

        # Step 5: First-degree metrics (pandas)
        step_start = time.time()
        customer_cifs = {ctx.cif_no for ctx in contexts}
        first_degree_df = _cached_pandas(
            cache, "first_degree",
            compute_pd._compute_first_degree, self.edges, context_df, params, customer_cifs,
        )
        self._metrics.step_times["first_degree"] = time.time() - step_start
        logger.info(
            f"[Step 5/6] First-degree metrics computed ({self._metrics.step_times['first_degree']:.2f}s): "
            f"{len(first_degree_df)} customer-counterparty pairs"
        )

        # Step 6: Second-degree + assemble
        step_start = time.time()
        second_degree_df = _cached_pandas(
            cache, "second_degree",
            compute_pd._compute_second_degree,
            self.edges, self.nodes, first_degree_df, context_df,
            risk_pd, params, skip_network, skip_connected_compliance,
        )
        self._metrics.step_times["second_degree"] = time.time() - step_start
        logger.info(
            f"[Step 6/6] Second-degree metrics computed ({self._metrics.step_times['second_degree']:.2f}s)"
        )

        step_start = time.time()
        self._results = compute_pd._assemble(
            first_degree_df, second_degree_df, self.nodes, contexts, params
        )
        self._metrics.step_times["assemble"] = time.time() - step_start

        self._finalize_metrics(start_time)

    def _extract_txns(
        self,
        transactions: DataFrame,
        account_master: DataFrame,
        context_df: pd.DataFrame,
    ) -> DataFrame:
        """Extract CIF-scoped transaction subset via Spark."""
        spark_context = compute_spark._compute_context_df(
            self._spark,
            [CaseContext(cif_no=r["cif_no"], review_date=r["review_date"])
             for _, r in context_df.iterrows()],
            self._params,
        )

        bounds = spark_context.agg(
            F.min("lifetime_start").alias("broad_start"),
            F.max("review_date").alias("broad_end"),
        ).first()

        all_cifs = list(context_df["cif_no"])

        broad_txns = transactions.filter(
            F.col("transaction_date").between(bounds["broad_start"], bounds["broad_end"])
        )
        cust_txns = broad_txns.filter(F.col("cif_no").isin(all_cifs))
        cp_accounts = [
            r["counterparty_bank_account"]
            for r in cust_txns.select("counterparty_bank_account").distinct().collect()
        ]

        cp_cifs = [
            r["cif_no"]
            for r in account_master.filter(
                F.col("foracid").isin(cp_accounts)
            ).select("cif_no").distinct().collect()
        ]

        all_extract_cifs = list(set(all_cifs + cp_cifs))
        return broad_txns.filter(
            F.col("cif_no").isin(all_extract_cifs)
            | F.col("counterparty_bank_account").isin(cp_accounts)
        ).select(
            "cif_no", "counterparty_bank_account", "counterparty_name",
            "transaction_date", "direction", "amount",
        )

    def _extract_to_cache(
        self,
        cache: _ComputeCache,
        transactions: DataFrame,
        account_master: DataFrame,
        context_df: pd.DataFrame,
        risk_scores: Optional[DataFrame],
        labels: Optional[DataFrame],
        kyc: Optional[DataFrame],
    ):
        """Use Spark to extract relevant data subsets to parquet for pandas."""
        if not cache.has("input_account_master"):
            cache.write_spark("input_account_master", account_master)

        _cached(
            cache, "input_txns",
            self._extract_txns,
            transactions, account_master, context_df,
        )

        if labels is not None and not cache.has("input_labels"):
            cache.write_spark("input_labels", labels)

        if kyc is not None and not cache.has("input_kyc"):
            cache.write_spark("input_kyc", kyc)

        if risk_scores is not None and not cache.has("input_risk_scores"):
            cache.write_spark("input_risk_scores", risk_scores)

    # --- Engine-specific properties ---

    @property
    def edge_count(self) -> int:
        return len(self.edges) if self.edges is not None else 0

    @property
    def node_count(self) -> int:
        return len(self.nodes) if self.nodes is not None else 0

    @property
    def internal_ratio(self) -> float:
        if self.edges is None or len(self.edges) == 0:
            return 0.0
        return float(self.edges["target_is_internal"].sum()) / len(self.edges)

    def get_node(self, cif_no: str) -> Optional[dict]:
        if self.edges is None:
            return None

        node_attrs = {}
        if self.nodes is not None:
            match = self.nodes[self.nodes["node_cif"] == cif_no]
            if len(match) > 0:
                node_attrs = match.iloc[0].to_dict()

        cp = self.edges[self.edges["source"] == cif_no]
        cp_agg = (
            cp.groupby(["target", "target_name", "target_is_internal"])
            .agg(txn_count=("amount", "count"), total_amount=("amount", "sum"))
            .reset_index()
        )

        counterparties = [
            {
                "target": r["target"],
                "target_name": r["target_name"],
                "is_internal": bool(r["target_is_internal"]),
                "txn_count": int(r["txn_count"]),
                "total_amount": float(r["total_amount"]),
            }
            for _, r in cp_agg.iterrows()
        ]

        return {"node_attrs": node_attrs, "counterparties": counterparties}

    def _save_edges(self, path: str, overwrite: bool) -> None:
        if self.edges is not None:
            self.edges.to_parquet(
                os.path.join(path, "edges.parquet"), index=False,
                coerce_timestamps="us", allow_truncated_timestamps=True,
            )

    def _save_nodes(self, path: str, overwrite: bool) -> None:
        if self.nodes is not None:
            self.nodes.to_parquet(
                os.path.join(path, "nodes.parquet"), index=False,
                coerce_timestamps="us", allow_truncated_timestamps=True,
            )


# =============================================================================
# Factory functions
# =============================================================================


def create_counterparty_graph(
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
    engine: Literal["spark", "pandas"] = "spark",
) -> Union[SparkCounterpartyGraph, PandasCounterpartyGraph]:
    """
    Create and compute a counterparty graph.

    Args:
        engine: "spark" (default) or "pandas".
            - "spark": All compute via PySpark. Works at any scale.
            - "pandas": Spark extracts data → parquet cache → pandas computes.
              Requires cache_path + batch_id. Fast for small batches (< 100 CIFs).

    Returns:
        SparkCounterpartyGraph or PandasCounterpartyGraph with computed results.
    """
    if engine == "pandas" and contexts and not (cache_path and batch_id):
        raise ValueError(
            "engine='pandas' requires cache_path and batch_id "
            "(Spark extracts data to parquet, pandas reads it)"
        )

    # Early return for empty contexts
    if not contexts:
        if engine == "pandas":
            instance = PandasCounterpartyGraph(spark, contexts, params, skip_network, skip_connected_compliance)
        else:
            instance = SparkCounterpartyGraph(spark, contexts, params, skip_network, skip_connected_compliance)
        logger.info("[CounterpartyGraph] No contexts provided, returning empty results")
        return instance

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
        f"[CounterpartyGraph] engine={engine}, "
        f"params: lifetime={params.lifetime_lookback_months}mo, "
        f"network={params.network_lookback_months}mo, hub_threshold={params.hub_threshold}, "
        f"skip_network={skip_network}, skip_compliance={skip_connected_compliance}"
    )

    if engine == "pandas":
        instance = PandasCounterpartyGraph(spark, contexts, params, skip_network, skip_connected_compliance)
        instance._run(transactions, account_master, risk_scores, labels, kyc, cache)
    else:
        instance = SparkCounterpartyGraph(spark, contexts, params, skip_network, skip_connected_compliance)
        instance._run(transactions, account_master, risk_scores, labels, kyc, cache)

    return instance


def load_counterparty_graph(spark: SparkSession, path: str) -> SparkCounterpartyGraph:
    """Reload a saved counterparty graph from disk. Returns SparkCounterpartyGraph."""
    return _CounterpartyGraphBase._load_common(spark, path)
