"""
Graph-first Counterparty Graph — PySpark Implementation

Computes counterparty graphs for a batch of AML cases in one pass.
Identity resolution via account_master, per-customer date windows,
single-scan edge table for 2nd-degree network analysis.

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
from datetime import datetime
from typing import Dict, List, Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .cache import _ComputeCache, _cached
from .compute import (
    _assemble,
    _build_edge_table,
    _build_node_attributes,
    _compute_context_df,
    _compute_first_degree,
    _compute_second_degree,
)
from .models import (
    BatchMetrics,
    CaseContext,
    CustomerGraph,
    GraphParameters,
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

        # Step 2: Build edge table (single-scan identity resolution)
        step_start = time.time()
        self.edges = _cached(
            cache, "edge_table",
            lambda: _build_edge_table(transactions, account_master, context_df),
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
        # Single aggregation to collect both source CIFs and internal target CIFs,
        # instead of two separate .collect() passes over the cached edge table.
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
            lambda: _build_node_attributes(spark, labels, kyc, edge_cifs),
        )
        self._metrics.step_times["node_attrs"] = time.time() - step_start
        logger.info(
            f"[Step 3/6] Node attributes built ({self._metrics.step_times['node_attrs']:.2f}s): "
            f"{len(edge_cifs)} nodes ({len(source_cifs)} sources, {len(internal_targets)} internal targets), "
            f"labels={'yes' if labels is not None else 'no'}, kyc={'yes' if kyc is not None else 'no'}"
        )

        # Step 4: Compute 1st-degree metrics
        step_start = time.time()
        customer_cifs = {ctx.cif_no for ctx in contexts}
        first_degree_df = _cached(
            cache, "first_degree",
            lambda: _compute_first_degree(self.edges, context_df, params, customer_cifs),
        )
        first_degree_count = first_degree_df.count()
        self._metrics.step_times["first_degree"] = time.time() - step_start
        logger.info(
            f"[Step 4/6] First-degree metrics computed ({self._metrics.step_times['first_degree']:.2f}s): "
            f"{first_degree_count} customer-counterparty pairs"
        )

        # Step 5: Compute 2nd-degree metrics
        step_start = time.time()
        second_degree_df = _cached(
            cache, "second_degree",
            lambda: _compute_second_degree(
                self.edges, self.nodes, first_degree_df, context_df,
                risk_scores, params, skip_network, skip_connected_compliance,
            ),
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
