# Counterparty Graph Module

Graph-first counterparty network analysis for AML case review. Computes counterparty graphs for a batch of cases in one pass, with dual-engine support (PySpark or Pandas).

## Quick Start

```python
from counterparty import (
    create_counterparty_graph,
    load_counterparty_graph,
    CaseContext,
    GraphParameters,
)
from datetime import date

# Define cases to review
contexts = [
    CaseContext(cif_no="CIF-001", review_date=date(2024, 6, 15)),
    CaseContext(cif_no="CIF-002", review_date=date(2024, 7, 1)),
]

# Spark engine (default) — works at any scale
graph = create_counterparty_graph(
    spark, transactions, account_master, contexts,
    params=GraphParameters(),
    risk_scores=risk_scores,
    labels=labels,
    kyc=kyc,
)

# Pandas engine — fast for small batches (< 100 CIFs)
graph = create_counterparty_graph(
    spark, transactions, account_master, contexts,
    engine="pandas",
    cache_path="/data/cache",
    batch_id="run_001",
)

# Access results
customer = graph.get_customer("CIF-001")
print(customer.profile)                    # CustomerProfile
print(customer.summary)                    # total/internal/external/hub counts
print(customer.counterparties["CIF-X"])    # CounterpartyEntry

# Inspect raw graph
print(graph.edge_count, graph.node_count, graph.internal_ratio)

# Save + reload
graph.save("/data/graphs/batch_2024_06")
loaded = load_counterparty_graph(spark, "/data/graphs/batch_2024_06")

# Visualize
graph.visualize(customer_cif="CIF-001", output_path="network.html")
```

## Engines

| Engine | Class | Best For | How It Works |
|--------|-------|----------|--------------|
| `"spark"` | `SparkCounterpartyGraph` | Large batches, cluster | All compute via PySpark DataFrames |
| `"pandas"` | `PandasCounterpartyGraph` | Small batches (< 100 CIFs) | Spark extracts data → parquet cache → Pandas computes |

Both engines produce identical results. The Pandas engine requires `cache_path` + `batch_id` because it uses Spark only for the initial data extraction, then switches to Pandas for all computation.

## Cache

`_ComputeCache` stores intermediate DataFrames as parquet files under `{cache_path}/{batch_id}/{step}.parquet`. Works with both local paths and HDFS (`hdfs://...`) via Hadoop filesystem API.

**Cached steps:** `edge_table`, `node_attrs`, `first_degree`, `second_degree` (Spark engine), plus `input_txns`, `input_account_master`, `input_labels`, `input_kyc`, `input_risk_scores` (Pandas engine extraction).

```python
# Enable caching (both engines)
graph = create_counterparty_graph(
    spark, transactions, account_master, contexts,
    cache_path="/data/cache", batch_id="run_001",
)

# Force recompute
graph = create_counterparty_graph(
    ..., cache_path="/data/cache", batch_id="run_001", overwrite_cache=True,
)
```

## Input DataFrames

| DataFrame | Required Columns | Description |
|-----------|-----------------|-------------|
| `transactions` | `cif_no, transaction_date, counterparty_bank_account, counterparty_name, direction, amount` | All transactions |
| `account_master` | `foracid, cif_no` | Account → customer mapping (identity resolution) |
| `risk_scores` | `cif_no, observation_date, score` | Daily risk scores (optional) |
| `labels` | `cif_no, isL2, isSAR, alert_generated_date, case_date_open, case_date_close` | Compliance lifecycle (optional) |
| `kyc` | `cif_no, segment, declared_income` | Static customer profiles (optional) |

## Models

### Input

- **`CaseContext`** — Customer CIF + review date, optional event/baseline overrides
- **`GraphParameters`** — Tunable thresholds (lookback windows, hub threshold, spike ratio, risk cutoffs)

### Output

```
CustomerGraph
├── profile: CustomerProfile          # reviewed customer's own profile
│     ├── cif_no, score, risk_rating, segment, declared_income
│     └── alert_count, case_count, sar_count, has_open_case
├── counterparties: Dict[target_id → CounterpartyEntry]
│     ├── counterparty_account, counterparty_name, target_is_internal
│     ├── relationship: RelationshipProfile
│     ├── lifetime_summary: LifetimeSummary
│     ├── event_periods: Dict["event" → EventPeriodAggregates]
│     ├── baseline_period: BaselinePeriodAggregates
│     ├── event_vs_baselines: Dict["event" → EventVsBaseline]
│     ├── network: NetworkPosition (hub detection)
│     ├── compliance_own: ComplianceOwn (internal only)
│     ├── compliance_connected: ComplianceConnected
│     ├── internal_profile: InternalProfile | None
│     └── external_profile: ExternalProfile | None
└── summary: CustomerSummary
      └── total_counterparties, internal_count, external_count,
          hub_counterparties, high_risk_counterparties
```

### Batch

- **`BatchMetrics`** — Total/unique counterparties, transactions scanned, per-step timing, skip flags

## Results API

| Method / Property | Returns | Description |
|-------------------|---------|-------------|
| `graph.get_customer(cif)` | `CustomerGraph \| None` | Full analysis for one customer |
| `graph.results` | `Dict[str, CustomerGraph]` | All computed results |
| `graph.metrics` | `BatchMetrics` | Computation metrics |
| `graph.get_node(cif)` | `dict \| None` | Raw node attributes + counterparty list |
| `graph.edge_count` | `int` | Total edges in graph |
| `graph.node_count` | `int` | Total nodes in graph |
| `graph.internal_ratio` | `float` | Fraction of edges to internal counterparties |

## Persistence

`graph.save(path)` writes:
- `results.json` — serialized `CustomerGraph` dict (human-readable)
- `edges.parquet` — resolved edge table
- `nodes.parquet` — node attributes
- `metadata.json` — edge_count, node_count, timestamp, `BatchMetrics`, `GraphParameters`

`load_counterparty_graph(spark, path)` restores from disk. `get_customer()` and `visualize()` work immediately.

## Visualization

Interactive HTML via vis.js with force-directed layout.

| Node Type | Color | Shape |
|-----------|-------|-------|
| Customer | Blue (#4A90D9) | dot (large) |
| Internal, low risk | Green (#7EC850) | dot |
| Internal, medium risk | Orange (#F5A623) | dot |
| Internal, high risk | Red (#D0021B) | dot (thick border) |
| External | Gray (#9B9B9B) | diamond |
| Hub (any) | same color | star |

| Edge Condition | Color | Style |
|---------------|-------|-------|
| Normal | Gray (#CCCCCC) | solid, width proportional to log(amount) |
| Volume spike | Red (#D0021B) | solid |
| New relationship | Orange (#F5A623) | dashed |

Controls: toggle external nodes, toggle labels. Hover for detailed tooltips.

```python
graph.visualize(customer_cif="CIF-001", output_path="network.html")
graph.visualize(title="Full Batch", output_path="batch.html")  # all customers
```

## Architecture

### Class Hierarchy

```
_CounterpartyGraphBase (ABC)
  ├── Stores: spark, contexts, params, skip flags, results, metrics
  ├── Results API: get_customer(), results, metrics
  ├── Persistence: save(), _load_common()
  ├── Visualization: visualize()
  │
  ├── SparkCounterpartyGraph
  │     ├── edges: Optional[pyspark.DataFrame]
  │     ├── nodes: Optional[pyspark.DataFrame]
  │     └── _run(transactions, account_master, risk_scores, labels, kyc, cache)
  │
  └── PandasCounterpartyGraph
        ├── edges: Optional[pd.DataFrame]
        ├── nodes: Optional[pd.DataFrame]
        └── _run(transactions, account_master, risk_scores, labels, kyc, cache)
```

### 6-Step Pipeline

Both engines follow the same pipeline:

```
create_counterparty_graph()
  ├── Step 1: _compute_context_df()     → per-customer date bounds
  ├── Step 2: _build_edge_table()       → identity resolution via account_master
  ├── Step 3: _build_node_attributes()  → compliance + KYC per node
  ├── Step 4: _compute_first_degree()   → relationship, lifetime, event, baseline metrics
  ├── Step 5: _compute_second_degree()  → network (hub), connected compliance, risk scores
  └── Step 6: _assemble()               → join all → Dict[cif_no, CustomerGraph]
```

The Pandas engine adds an extraction step before Step 2: Spark scopes the data to relevant CIFs and writes parquet files that Pandas reads.

### Key Design Decisions

**Identity resolution via `account_master`:** The `account_master` table (`foracid → cif_no`) is the single source of truth. If a `counterparty_bank_account` maps to a CIF → internal. Otherwise → external. Self-loops removed.

**Per-customer date windows:** Each customer has independent date bounds based on their `review_date` — lifetime, event, baseline, network, and rating windows are all relative.

**Factory pattern:** `create_counterparty_graph()` constructs the instance, calls `_run()`, and returns a fully computed graph. Consumers never call `_run()` directly.

## Parameters (`GraphParameters`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lifetime_lookback_months` | 24 | Lookback for 1st degree transactions |
| `network_lookback_months` | 12 | Lookback for 2nd degree network |
| `rating_lookback_months` | 12 | Lookback for risk score window |
| `default_event_months` | 3 | Default event period length |
| `default_baseline_months` | 6 | Default baseline period length |
| `hub_threshold` | 5 | Min connections to be flagged as hub |
| `volume_spike_threshold` | 2.0 | Event/baseline ratio for spike detection |
| `rating_high_threshold` | 0.7 | Score threshold for "high" risk |
| `rating_medium_threshold` | 0.4 | Score threshold for "medium" risk |

## Tests

```bash
# Requires Java 17+ for PySpark
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home

cd /path/to/aml_copilot
poetry run pytest counterparty/tests/ -v
```

| Test File | Coverage |
|-----------|----------|
| `test_edge_table.py` | Identity resolution, self-loops, internal flag, 2nd degree inclusion |
| `test_node_attributes.py` | Compliance aggregation, open case detection, KYC, null inputs |
| `test_first_degree.py` | Lifetime aggregates, event/baseline filtering, spike detection, bidirectional |
| `test_second_degree.py` | Inbound/outbound connections, hub detection, compliance, risk scores, skip flags |
| `test_integration.py` | Full pipeline, result structure, save/load, get_customer, batch metrics |
| `test_viz.py` | vis.js nodes/edges, colors, shapes, HTML rendering, controls, single-customer filter |
