# Counterparty Graph Module

Graph-first counterparty network analysis for AML case review. Computes counterparty graphs for a batch of cases in one pass using PySpark.

## Architecture

```
CounterpartyGraph.__init__()
  ├── _compute_context_df()     → per-customer date bounds
  ├── _build_edge_table()       → two-pass identity resolution
  │     ├── Pass 1: reviewed customers' transactions (1st degree)
  │     ├── Pass 2: counterparties' own transactions (2nd degree)
  │     └── Resolve identities via account_master + remove self-loops
  ├── _build_node_attributes()  → compliance + KYC per node
  ├── _compute_first_degree()   → relationship, lifetime, event, baseline metrics
  ├── _compute_second_degree()  → network (hub), connected compliance, risk scores
  └── _assemble()               → join all → Dict[cif_no, CustomerGraph]
```

## Quick Start

```python
from counterparty import CounterpartyGraph, CaseContext, GraphParameters
from datetime import date

# Define cases to review
contexts = [
    CaseContext(cif_no="CIF-001", review_date=date(2024, 6, 15)),
    CaseContext(cif_no="CIF-002", review_date=date(2024, 7, 1)),
]

# Build + compute in one step
graph = CounterpartyGraph(
    spark, transactions, account_master, contexts,
    params=GraphParameters(),
    risk_scores=risk_scores,
    labels=labels,
    kyc=kyc,
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
loaded = CounterpartyGraph.load(spark, "/data/graphs/batch_2024_06")

# Visualize
graph.visualize(customer_cif="CIF-001", output_path="network.html")
```

## Input DataFrames

| DataFrame | Required Columns | Description |
|-----------|-----------------|-------------|
| `transactions` | `cif_no, transaction_date, counterparty_bank_account, counterparty_name, direction, amount` | All transactions |
| `account_master` | `foracid, cif_no` | Authoritative account → customer mapping |
| `risk_scores` | `cif_no, observation_date, score` | Daily risk scores (optional) |
| `labels` | `cif_no, isL2, isSAR, alert_generated_date, case_date_open, case_date_close` | Compliance lifecycle (optional) |
| `kyc` | `cif_no, segment, declared_income` | Static customer profiles (optional) |

## Key Design Decisions

### Identity Resolution via `account_master`

The old `counterparty_cif_id` field was unreliable. Now `account_master` (foracid → cif_no) is the single source of truth:
- If `counterparty_bank_account` maps to a CIF → internal (`target_is_internal=True`)
- Otherwise → external (target = raw account string)
- Self-loops (CIF transacts with own account) are removed

### Two-Pass Edge Table

1st degree only needs reviewed customers' transactions, but 2nd degree needs the broader network:
- **Pass 1**: Reviewed customers' txns within their lifetime window
- **Pass 2**: Counterparties' own outbound txns + non-reviewed customers' inbound txns to counterparty accounts
- Both passes combined, deduped, then identity-resolved

### Per-Customer Date Windows

Each customer has independent date bounds based on their `review_date`:
- `lifetime_start = review_date - lifetime_lookback_months`
- `event_start/end` = event period (default: 3 months before review)
- `baseline_start/end` = baseline period (default: 6 months before event)
- `network_start = review_date - network_lookback_months`
- `rating_start = review_date - rating_lookback_months`

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

## Output Structure

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
      └── total_counterparties, internal_count, external_count, hub_counterparties, high_risk_counterparties
```

## Persistence Format

`graph.save(path)` writes:
- `results.json` — serialized CustomerGraph dict (human-readable)
- `edges.parquet` — resolved edge table
- `nodes.parquet` — node attributes
- `metadata.json` — edge_count, node_count, timestamp, BatchMetrics, GraphParameters

`CounterpartyGraph.load(spark, path)` restores from disk — `get_customer()` and `visualize()` work immediately.

## Visualization

Interactive HTML via vis.js with force-directed layout:

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
| Normal | Gray (#CCCCCC) | solid, width ∝ log(amount) |
| Volume spike | Red (#D0021B) | solid |
| New relationship | Orange (#F5A623) | dashed |

Controls: toggle external nodes, toggle labels. Hover for detailed tooltips.

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
