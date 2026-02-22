# AML AI Review System — Architecture & Implementation Guide

## Purpose of This Document

This document is the complete technical specification for an AI-powered AML (Anti-Money Laundering) review system. It describes the full architecture, the reasoning behind every design decision, and the precise responsibilities of each component. Use this document as the authoritative reference when implementing any part of the system.

---

## System Philosophy

The system automates L1 (RFI) and L2 (SAR) compliance reviews for flagged banking customers. It is built on three principles:

1. **Deterministic logic does everything deterministic logic can do.** Scoring, event detection, indicator calculation, counterparty lookup, threshold comparison — these are computational tasks. They produce precise, reproducible, auditable outputs. No AI is used for any of these.

2. **AI operates in a constrained corridor where reasoning is genuinely required.** The AI evaluates what combinations of evidence mean in context, matches patterns to typologies, and generates investigative narratives. Its inputs are pre-computed and structured. Its outputs are structured. It does not query external systems or choose its own evaluation path.

3. **Every decision is regulator-defensible.** The system must be able to answer "why was this case reviewed this way?" at every step. Deterministic steps are reproducible. AI steps produce structured outputs with evidence citations and confidence levels.

### Where AI Is Genuinely Irreplaceable

The system uses AI for four capabilities that no rule engine or deterministic logic can replicate:

**Contextual interpretation of evidence combinations.** Individual flags are just numbers — "4 unknown counterparties," "74x income ratio," "98.7% pass-through rate." A rule engine sees separate flags. The AI sees: "this looks like a funnel account where individuals pool money through an intermediary for real estate purchases." The synthesis of multiple signals into a coherent hypothesis is reasoning, not computation. The number of possible flag combinations across customer types, business activities, and transaction patterns is too large to enumerate as rules.

**Typology matching as narrative pattern recognition.** Typology definitions are described in natural language: "Funnel accounts are characterized by multiple unrelated individuals depositing funds which are consolidated and forwarded to a single beneficiary, often with the account holder having no apparent economic reason to receive the funds." Matching case evidence against these descriptions is a semantic task. The AI reads the evidence, reads the typology definition, and determines whether the pattern fits. Encoding every typology as boolean conditions would be brittle, incomplete, and unable to handle fuzzy or overlapping patterns.

**KYC-contextual evaluation that shapes the investigation.** A 74x income ratio for a salaried employee means something very different than a 5x average-month ratio for a seasonal trading company. The same counterparty pattern means different things for an import/export business vs. a retail employee. The AI interprets pre-computed metrics in the context of the customer's specific profile — their declared activity, their business type, their customer segment — and produces findings that frame the rest of the investigation. This context-setting cannot be reduced to rules because the interpretation depends on unstructured KYC declarations (free-text business descriptions, declared activities) combined with quantitative metrics.

**Generating investigative narratives.** The final report isn't a list of flags. It's a coherent story that connects evidence to concern to recommendation, written in language that a reviewer or regulator can act on. This requires understanding cause, intent, and investigative significance.

### Where AI Is NOT Used (and Why)

| Task | Method | Why Not AI |
|------|--------|-----------|
| Risk score computation | ML model inference | Deterministic, reproducible |
| Event detection (behavioral change) | Statistical shift detection | Mathematical, not interpretive |
| Indicator breach evaluation | Threshold comparison | Arithmetic |
| Transaction pulling | Rule-based selection | Deterministic mapping from indicators |
| Counterparty graph lookup | Pre-computed graph query | Database operation |
| Decision aggregation | Rule-based on structured outputs | Must be reproducible |
| Graph traversal / path selection | Conditional edges on finding_type | Deterministic routing |

---

## Architecture Overview

The system operates in 6 sequential stages. Stages 1–4 are fully deterministic and produce the case evidence package. Stage 5 is the AI-assisted decision graph. Stage 6 is AI-assisted report generation.

```
Stage 1: Scoring (ML model)
    ↓ continuous risk score time series
Stage 2: Event Detection (statistical)
    ↓ event windows with temporal boundaries
Stage 3: Indicators & Transaction Pulling (rule-based)
    ↓ breaching indicators + pulled transactions
Stage 4: Enrichment (graph + lookup)
    ↓ complete case JSON
Stage 5: Decision Graph Navigation (AI agent)
    ↓ structured findings per node
Stage 6: Report Generation (AI agent)
    ↓ investigative narrative
```

---

## Stage 1: Scoring

**What it does:** An ML model produces a continuous risk score for each customer over time. The score is retained as a time series — not just the current value, but the full trajectory.

**Output:** Score history per customer (time series).

**Critical design decision:** Scores are used ONLY for event detection (Stage 2). They detect WHEN behavior changed, not WHETHER the behavior is suspicious. Scores are never used directly for risk determination or decision-making. This is because:
- Scores are correlation-based, not causal
- Model accuracy degrades significantly for medium-risk customers (the majority of alert volume)
- Using scores only for temporal detection avoids depending on the least reliable part of the model for the most important determination

---

## Stage 2: Event Detection

**What it does:** Statistical shift detection algorithms analyze the score time series to identify when a meaningful behavioral change occurred.

**Method:** Change-point detection on the score history. When the score shifts significantly from its historical baseline, the system identifies:
- **Event window:** The period during which the behavioral change occurred
- **Baseline period:** The reference period before the change (typically 30 days)

**Output:** Event windows with temporal boundaries (start date, end date, baseline start, baseline end).

---

## Stage 3: Indicators & Transaction Pulling

**What it does:** Compares the event period against the baseline period across six dimensions. Each dimension that breaches its threshold becomes a triggered indicator. Each triggered indicator pulls specific transactions for review.

### The Six Indicators

| Indicator | What It Measures | Comparison |
|-----------|-----------------|------------|
| Transaction Size | Average transaction amount | Event period avg vs. baseline avg |
| Velocity | Transaction count | Event period count vs. baseline count |
| Jurisdiction Risk | % transactions involving high-risk geographies | Event period % vs. baseline % |
| Counterparty Diversity | Number of new/unique counterparties | Event period new CPs vs. baseline |
| Rapid Movement | Credits matched by debits within 48h | Event period % vs. baseline % |
| Round Amounts | % of transactions at round numbers | Event period % vs. baseline % |

### Transaction Pulling

Each breaching indicator triggers specific transaction pulls:
- Size breach → pulls transactions above a size threshold
- Velocity breach → pulls transactions during high-activity periods
- Jurisdiction breach → pulls transactions involving flagged jurisdictions
- Counterparty diversity breach → pulls transactions with new counterparties
- Rapid movement breach → pulls credit-debit pairs within the 48h window
- Round amounts breach → pulls round-amount transactions

**Critical:** Pulled transactions retain metadata about which indicator triggered their selection. This is used in the decision graph to link evidence to indicators.

**Output:** List of breaching indicators + pulled transactions with trigger metadata.

**Note:** The number of breaching indicators is itself a risk signal — more indicators breaching simultaneously suggests more dimensions of behavioral change.

---

## Stage 4: Enrichment

**What it does:** Assembles the complete case context that the AI agent will need. After this stage, no external queries are made during the review — all data is in the case JSON.

### 4.1 Counterparty Graph

The counterparty graph provides the AI decision graph with a complete picture of every counterparty involved in a flagged case. For each counterparty, the graph answers three questions:

1. **How well do we know this counterparty?** Are they our customer? Have they been cleared before? How long has the relationship existed? Is this a new or established connection?
2. **How much money flows between them and the customer?** What are the volumes, frequencies, and patterns over the lifetime of the relationship and during the event period specifically?
3. **Is there anything concerning about them?** What is their risk score? Are they linked to SARs or alerts? Do they connect to other high-risk entities?

The graph is pre-computed and continuously updated. At review time, the system performs lookups, not computation. The case JSON for each review includes the full counterparty profile for every counterparty in the pulled transactions.

#### Where the Graph Is Consumed

- **Node 2 (Source of Funds):** Primary consumer. Uses the graph to evaluate each counterparty against the explanation hierarchy: cleared → known → unknown. Determines blocking vs. accumulating findings.
- **Node 3 (Economic Justification):** Uses relationship history and flow patterns to evaluate whether the transaction activity makes economic sense for the customer-counterparty pair.
- **Node 4 (Typology Matching):** Uses network characteristics (hub status, connected SAR count, unidirectional flow patterns) as inputs to typology pattern matching.
- **Report Generation:** Counterparty details are cited in the investigation narrative.

#### Counterparty Identification

Every transaction carries a beneficiary or originator account number. This is the universal counterparty identifier — it appears regardless of whether the counterparty is internal or external.

**Internal counterparties:** When a counterparty's account number belongs to our bank, it resolves to an internal customer ID. This gives access to the customer's risk score, KYC profile, transaction history, and alert/SAR history. Internal counterparties have a rich profile.

**External counterparties:** When the account number is not ours, we only know what the transaction provides: name, account number, bank, and reference text. Risk for external counterparties is inferred from their network position and the scores of their internal connections (see Counterparty Risk Score below).

#### Edge Properties: The Relationship

An edge represents the full relationship between a customer and a counterparty. It is keyed by the customer-counterparty account pair. Direction (inbound/outbound) is a property of the edge, not a separate edge.

**Relationship Profile:**

| Property | Description | Why It Matters |
|----------|-------------|----------------|
| first_transaction_date | Date of the very first transaction between this customer and counterparty, across all time | Distinguishes new relationships from established ones. A counterparty first seen during the event period is more suspicious than one with 2 years of history. |
| last_transaction_date | Date of the most recent transaction | Identifies dormant relationships. Combined with first_transaction_date, gives relationship span. |
| relationship_duration_months | Months between first and last transaction | Direct measure of relationship maturity |
| months_active | Number of distinct months with at least one transaction | A 12-month relationship with only 2 active months is very different from one with 12 active months |
| is_new_in_event_period | Boolean: first_transaction_date falls within the event window | Critical flag. New counterparties appearing during behavioral change are a primary SOF concern. |
| is_bidirectional | Boolean: transactions exist in both directions | Bidirectional flows suggest a bilateral commercial or personal relationship. Unidirectional flows suggest dependency or pass-through. |
| activity_consistency | Categorical: regular, intermittent, burst, new, dormant_reactivated | Characterizes the pattern of the relationship over its lifetime. Dormant relationships that reactivate during an event period are a distinct signal. |

**Activity Consistency Definitions:**

| Value | Definition |
|-------|-----------|
| regular | Transactions in >70% of months within the relationship span. Consistent, predictable pattern. (70% threshold is configurable via `activity_regular_threshold`) |
| intermittent | Transactions in 30–70% of months. Some months active, some not. Irregular but not unusual. |
| burst | Transactions in <30% of months, but concentrated. High activity in a short window, quiet otherwise. |
| new | Relationship duration < 3 months. Not enough history to characterize the pattern. (3 months is configurable via `new_relationship_months`) |
| dormant_reactivated | No transactions for >3 months, then activity resumes. Computed by detecting a gap of 3+ inactive months followed by new transactions. (3 months is configurable via `dormancy_gap_months`) |

Activity consistency is computed deterministically from monthly transaction aggregates. No AI is needed.

**Transaction Aggregates — Lifetime Summary:**

Aggregated across the full history of the relationship (within the configurable `lifetime_lookback_months` window):

| Property | Description |
|----------|-------------|
| total_inbound_count | Total transactions received from counterparty |
| total_inbound_amount | Total amount received from counterparty |
| total_outbound_count | Total transactions sent to counterparty |
| total_outbound_amount | Total amount sent to counterparty |
| net_flow | total_inbound_amount − total_outbound_amount |
| avg_monthly_inbound | Average inbound amount per active month |
| avg_monthly_outbound | Average outbound amount per active month |

**Transaction Aggregates — Event Period:**

| Property | Description |
|----------|-------------|
| inbound_count | Transactions received in event period |
| inbound_amount | Total received in event period |
| outbound_count | Transactions sent in event period |
| outbound_amount | Total sent in event period |
| round_amount_count | Count of round-number transactions in event period |
| common_references | Most frequent transaction reference text(s) |
| reference_diversity | Count of distinct reference texts |
| first_txn | Earliest transaction date in event period |
| last_txn | Latest transaction date in event period |

**Transaction Aggregates — Baseline Period:**

Same structure as event period (inbound_count, inbound_amount, outbound_count, outbound_amount) but for the baseline window.

**Event vs. Baseline Comparison (per counterparty):**

| Property | Description |
|----------|-------------|
| inbound_amount_change | Ratio: event inbound / baseline inbound |
| outbound_amount_change | Ratio: event outbound / baseline outbound |
| is_volume_spike | Boolean: change exceeds configured threshold (default 2x, configurable via `volume_spike_threshold`) |
| is_entirely_new | Boolean: baseline inbound and outbound are both zero |

Note: Stage 3 computes event-vs-baseline at the customer level across all transactions. This per-counterparty comparison adds granularity: the overall volume spike might be driven by one counterparty doubling while others stay flat. The AI at Node 3 needs to know which specific relationships changed, not just that the customer's aggregate behavior shifted.

#### Node Properties: The Counterparty

Each unique counterparty across the entire customer base is a node in the graph. Node properties describe who the counterparty is, how risky they are, and their position in the network.

**Internal Counterparty Profile:**

| Property | Source |
|----------|--------|
| is_internal_customer | Account number lookup (boolean) |
| internal_customer_id | Account number lookup |
| internal_max_score_Nm | Max risk score in last N months from review date (N is configurable via `score_lookback_months`, default 12) |
| internal_risk_rating | Current risk rating from KYC |
| internal_segment | Customer segment from KYC |
| internal_declared_income | Declared income from KYC |
| own_alert_count | Count of alerts on this customer |
| own_sar_count | Count of SARs filed on this customer |
| own_rfi_count | Count of RFIs sent for this customer |

**External Counterparty Profile:**

| Property | Source |
|----------|--------|
| is_internal_customer | Account number lookup (false) |
| weighted_avg_score | Computed from internal connections (see Counterparty Risk Score below) |
| connected_internal_customer_count | Count of our customers who transact with this counterparty |
| connected_high_risk_count | Count of connected internal customers with high risk rating |
| linked_to_sar_count | Count of SARs where this counterparty is named |
| linked_to_alert_count | Count of alerts involving this counterparty |

**Network Position Properties (both internal and external):**

| Property | Description | Why It Matters |
|----------|-------------|----------------|
| counterparty_account | Account number | Universal identifier |
| counterparty_name | Full name as it appears on transactions | Used for AI-based entity reasoning at Node 2 |
| counterparty_type | Categorical: individual, company, unknown. Inferred from name patterns or internal KYC if available. | Individuals and companies have different expected transaction patterns. An individual acting as a hub is more suspicious than a company acting as a hub. |
| connected_customer_count | How many of our customers transact with this counterparty | 1–2 connections = personal/business contact. 10+ = either a commercial entity (landlord, supplier) or a suspicious hub. |
| is_hub | Boolean: connected_customer_count exceeds configured threshold (`hub_threshold`, default 10) | Hubs that are NOT known commercial entities are suspicious. |
| hub_score | Ratio of this counterparty's connection count to the average connection count across all counterparties | Normalized measure of how unusual the connectivity is |

**Prior Clearance (per customer-counterparty relationship, not per counterparty globally):**

| Property | Description |
|----------|-------------|
| has_prior_clearance | Boolean: was this counterparty cleared in a prior review for this customer? |
| clearance_conditions | Free text: what was the clearance scope? (e.g., "Metals trading up to $500k/quarter") |
| clearance_date | Date of the review that cleared this counterparty |
| clearance_review_id | Link to the review that produced the clearance |

A counterparty cleared for one customer is NOT automatically cleared for another. The clearance reflects the specific investigation and business justification that was accepted. Node 2 must check clearance specific to the customer under review.

#### Counterparty Risk Score

**Internal Counterparty Score:**

The risk score is the maximum value of the customer's own risk score over the last N months from the review date (configurable via `score_lookback_months`, default 12).

Why max, not current: A customer whose score spiked to 0.9 three months ago and has since dropped to 0.5 still had that spike. The spike may have been the event that generated alerts. Using the max ensures the signal is not lost.

```
internal_max_score_Nm = MAX(daily_score)
  WHERE customer_id = counterparty's internal ID
  AND score_date BETWEEN (review_date - N months) AND review_date
```

**External Counterparty Score:**

External counterparties have no direct score. Their risk is inferred from the scores of the internal customers they transact with, weighted by transaction volume.

If an external counterparty transacts primarily with high-risk internal customers, they are more likely to be involved in suspicious activity. Volume weighting ensures material relationships dominate over incidental ones.

```
For each internal customer connected to this external counterparty:
  1. Get that customer's max_score_Nm (same window logic as internal)
  2. Get the total transaction volume between the external CP and that customer

weighted_avg_score = SUM(customer_max_score × transaction_volume) / SUM(transaction_volume)

Example:
  Customer A: max_score = 0.85, volume with CP = $500,000
  Customer B: max_score = 0.30, volume with CP = $50,000
  Customer C: max_score = 0.60, volume with CP = $200,000

  weighted_avg_score = (0.85×500k + 0.30×50k + 0.60×200k) / (500k + 50k + 200k)
                     = (425k + 15k + 120k) / 750k
                     = 0.747
```

When the external counterparty has no internal connections (connected_internal_customer_count = 0), weighted_avg_score is null. This means zero visibility into their risk — they are truly unknown. This is itself an important signal for Node 2.

**Score Snapshot Rule:** When assembling the case JSON, the counterparty score is computed as of the review date and stored in the case JSON. It does NOT update retroactively. The case record reflects what information was available when the review was conducted.

#### Entity Resolution: Name-Based AI Reasoning

Rather than building a separate entity resolution infrastructure, the system includes counterparty names as node properties and instructs the AI to reason about name similarities at review time. This leverages the LLM's natural strength at fuzzy name matching without requiring batch matching pipelines.

At Node 2, the AI performs three name-similarity assessments using the counterparty_name field from each counterparty and the customer's own name from the case JSON:

1. **Own-account detection:** Does any counterparty name closely match the customer's name? If so, the transaction may be a self-transfer between the customer's own accounts. Self-transfers combined with other flags (rapid movement, round amounts) suggest layering. Self-transfers in isolation may be routine.

2. **Counterparty consolidation:** Do any two counterparty names appear to be variants of the same person? Examples: "YAO ZENG" and "Y. ZENG", or "ZHIJUN YOU" and "ZHI JUN YOU". If so, the true concentration to that individual is the sum across their accounts. What appears as moderate amounts from two counterparties may actually be a large amount from one.

3. **Related-person patterns:** Do counterparty names share family names or other patterns suggesting familial or organizational relationships? The AI should note the pattern and consider whether it's consistent with a specific typology (e.g., family pooling for property purchase, or coordinated funnel account).

The AI includes its name-similarity assessment in the finding narrative with a stated likelihood, not a binary determination.

**Why this works without infrastructure:** LLMs are naturally strong at fuzzy name matching, especially for transliteration variants in Chinese, Arabic, and other non-Latin name systems. They recognize that "ZHIJUN YOU" and "ZHI JUN YOU" are likely the same person, and that "ZENG YAO" vs "YAO ZENG" is a family-name/given-name order swap.

**Limitation:** The AI only sees names within the current case. It cannot detect that "YAO ZENG" in this case is the same "Y. ZENG" appearing in 15 other customers' transactions. That cross-customer consolidation requires a future batch entity resolution pipeline.

**Required data:** No new fields needed. counterparty_name is already present on every counterparty. The customer's full name is already in the customer profile section. The only addition is the ENTITY REASONING instruction in the node prompt template.

#### Counterparty Graph Update Schedule

| Component | Update Frequency | Rationale |
|-----------|-----------------|-----------|
| Edge transaction aggregates (monthly granularity) | Daily | New transactions post daily. Monthly buckets updated incrementally. |
| Relationship profile (first_seen, duration, activity_consistency) | Daily | New transactions may create new relationships or update existing ones. |
| Internal counterparty scores (max_score_Nm) | Daily | Scores update daily as the ML model runs. |
| External counterparty scores (weighted_avg_score) | Daily | Depends on internal scores, which update daily. |
| Network properties (connected_customer_count, is_hub) | Daily | New transactions may connect a counterparty to additional customers. |
| SAR/Alert linkage counts | On event | Updated when a new SAR is filed or alert generated. Triggered, not scheduled. |
| Prior clearance records | On event | Updated when a review is completed and clearance conditions are set. |
| Entity resolution | Weekly batch (future) | Fuzzy matching across all counterparty names. More expensive, less time-sensitive. |

#### How the AI Uses Counterparty Graph Data

**Node 2 (Source of Funds) — Primary Consumer:**
- **Is this counterparty known?** is_internal_customer, has_prior_clearance, connected_customer_count, activity_consistency. An internal customer with a long relationship and regular activity is well-known. An external counterparty with activity_consistency = "new" and no prior clearance is unknown.
- **If known, is the current activity within bounds?** clearance_conditions vs. event_period amounts. is_volume_spike. If cleared for $500k/quarter and event shows $1.2M, the excess is flagged.
- **If unknown, how concerning?** internal_max_score_Nm or weighted_avg_score, linked_to_sar_count, linked_to_alert_count, is_hub. An unknown counterparty with a high inferred risk score and SAR linkages is much more concerning than one with no network signals.
- **What is the relationship context?** is_new_in_event_period, is_bidirectional, activity_consistency, relationship_duration_months. A new, unidirectional, burst relationship is treated very differently from a 2-year bidirectional regular relationship.

**Node 3 (Economic Justification) — Flow Patterns:**
- **Per-counterparty volume changes:** event_vs_baseline per counterparty. The overall customer volume spike might be driven by one relationship.
- **Transaction references:** common_references, reference_diversity. Vague or uniform references ("TRANSFER", "PERSONAL") across many transactions suggest structuring. Diverse references aligned with business activity suggest legitimate commerce.
- **Counterparty-to-counterparty flow:** If the customer receives from A, B, C and sends to D, the AI evaluates whether A→Customer→D represents a pass-through. The net_flow and is_bidirectional fields per counterparty reveal direction.

**Node 4 (Typology Matching) — Network Signals:**
- **Funnel account signal:** Multiple credit counterparties (all individual, all new, all unidirectional inbound) + single debit counterparty = classic funnel pattern.
- **Hub involvement:** If the main debit counterparty is_hub = true and has SAR linkages, funds are flowing toward a known collection point.
- **Network risk:** If multiple credit counterparties have elevated weighted_avg_score or SAR linkages, the entire inflow is suspect.

### 4.2 Compliance History

- Prior alerts on this customer
- Prior reviews and their outcomes
- Previous SARs or RFIs filed
- Prior clearance conditions (e.g., "counterparty X cleared for metals trading up to $500k/quarter")
- RFI responses received

### 4.3 KYC Records

- Customer profile: name, nationality, DOB, employment/business type
- Declared income or business turnover
- Declared business activity (free text)
- Customer risk rating
- PEP status, adverse media screening results
- Account opening date and relationship age

### 4.4 Case JSON Structure

The case JSON is a single document containing everything the agent needs. It is passed to the decision graph as the complete evidence package.

```json
{
  "customer": {
    "id": "...",
    "name": "...",
    "nationality": "...",
    "dob": "...",
    "segment": "retail | corporate | trade_finance | private_banking",
    "business_type": "employed | self_employed | company | freelancer",
    "declared_activity": "free text from KYC",
    "declared_income_monthly": 9000,
    "risk_rating": "low | medium | high",
    "pep_status": false,
    "adverse_media": false,
    "account_opened": "2024-01-18",
    "relationship_months": 19
  },
  "event": {
    "event_start": "2025-06-01",
    "event_end": "2025-08-03",
    "baseline_start": "2025-04-01",
    "baseline_end": "2025-05-31",
    "triggered_indicators": ["rapid_movement", "round_amounts"],
    "indicator_count": 2
  },
  "pre_computed_metrics": {
    "total_credits": 665882.68,
    "total_debits": 657510.95,
    "credit_to_debit_ratio": 0.987,
    "credits_to_declared_income_ratio": 74.0,
    "unique_credit_counterparties": 4,
    "unique_debit_counterparties": 1,
    "pct_round_amounts": 0.75,
    "rapid_movement_pct": 0.85,
    "new_counterparties_in_event": 4,
    "event_avg_txn_size": 41617.67,
    "baseline_avg_txn_size": null
  },
  "counterparty_graph": {
    "YAO ZENG": {
      "counterparty_account": "AE12 0340 0000 1234 5678 901",
      "counterparty_name": "YAO ZENG",

      "relationship": {
        "first_transaction_date": "2024-03-15",
        "last_transaction_date": "2025-07-28",
        "relationship_duration_months": 16,
        "months_active": 10,
        "is_new_in_event_period": false,
        "is_bidirectional": true,
        "activity_consistency": "intermittent"
      },

      "lifetime_summary": {
        "total_inbound_count": 23,
        "total_inbound_amount": 890000,
        "total_outbound_count": 5,
        "total_outbound_amount": 120000,
        "net_flow": 770000,
        "avg_monthly_inbound": 55625,
        "avg_monthly_outbound": 7500
      },

      "event_period": {
        "inbound_count": 5,
        "inbound_amount": 306500,
        "outbound_count": 0,
        "outbound_amount": 0,
        "round_amount_count": 4,
        "common_references": ["TRANSFER"],
        "reference_diversity": 1,
        "first_txn": "2025-06-05",
        "last_txn": "2025-07-28"
      },

      "baseline_period": {
        "inbound_count": 2,
        "inbound_amount": 85000,
        "outbound_count": 1,
        "outbound_amount": 30000
      },

      "event_vs_baseline": {
        "inbound_amount_change": 3.6,
        "outbound_amount_change": null,
        "is_volume_spike": true,
        "is_entirely_new": false
      },

      "counterparty_profile": {
        "is_internal_customer": true,
        "internal_customer_id": "CUST-29481",
        "internal_max_score_12m": 0.85,
        "internal_risk_rating": "high",
        "internal_segment": "retail",
        "internal_declared_income": 12000,
        "own_alert_count": 3,
        "own_sar_count": 1,
        "own_rfi_count": 2,
        "counterparty_type": "individual",
        "connected_customer_count": 2,
        "is_hub": false,
        "hub_score": 0.4,
        "has_prior_clearance": false,
        "clearance_conditions": null
      }
    },

    "PENGCHENG CHANG": {
      "counterparty_account": "CN58 1234 5678 9012 3456",
      "counterparty_name": "PENGCHENG CHANG",

      "relationship": {
        "first_transaction_date": "2025-06-10",
        "last_transaction_date": "2025-07-15",
        "relationship_duration_months": 1,
        "months_active": 2,
        "is_new_in_event_period": true,
        "is_bidirectional": false,
        "activity_consistency": "new"
      },

      "lifetime_summary": {
        "total_inbound_count": 3,
        "total_inbound_amount": 150000,
        "total_outbound_count": 0,
        "total_outbound_amount": 0,
        "net_flow": 150000,
        "avg_monthly_inbound": 75000,
        "avg_monthly_outbound": 0
      },

      "event_period": {
        "inbound_count": 3,
        "inbound_amount": 150000,
        "outbound_count": 0,
        "outbound_amount": 0,
        "round_amount_count": 3,
        "common_references": ["PERSONAL"],
        "reference_diversity": 1,
        "first_txn": "2025-06-10",
        "last_txn": "2025-07-15"
      },

      "baseline_period": {
        "inbound_count": 0,
        "inbound_amount": 0,
        "outbound_count": 0,
        "outbound_amount": 0
      },

      "event_vs_baseline": {
        "inbound_amount_change": null,
        "outbound_amount_change": null,
        "is_volume_spike": false,
        "is_entirely_new": true
      },

      "counterparty_profile": {
        "is_internal_customer": false,
        "weighted_avg_score": 0.62,
        "connected_internal_customer_count": 3,
        "connected_high_risk_count": 1,
        "linked_to_sar_count": 0,
        "linked_to_alert_count": 1,
        "counterparty_type": "individual",
        "connected_customer_count": 3,
        "is_hub": false,
        "hub_score": 0.6,
        "has_prior_clearance": false,
        "clearance_conditions": null
      }
    }
    // ... ZHIJUN YOU, JIANSHENG SUI, NOVA POWER REAL ESTATE LLC follow same structure
  },
  "compliance_history": {
    "prior_alerts": 0,
    "prior_reviews": [],
    "prior_sars": 0,
    "prior_rfis": 0,
    "clearance_conditions": []
  }
}
```

---

## Stage 5: Decision Graph Navigation

This is the core of the AI-assisted review. The agent navigates a 5-node decision graph. Each node asks a specific question, receives pre-computed inputs plus the case evidence, and produces a structured finding.

### Three-Layer Architecture

The decision at each node operates across three layers:

**Layer 1 — Deterministic Pre-Checks (computed before the agent runs):**
These are binary or numeric checks that the application logic resolves. The results are passed to the agent as pre-computed inputs. The agent does not re-compute these.
- Sanctions screening result (binary)
- Regulatory threshold breaches (numeric)
- Declared income vs. total credits (numeric ratio)
- Customer risk rating (lookup)
- PEP status (binary)
- Adverse media result (binary)

**Layer 2 — AI-Assisted Evaluation (the agent's work at each node):**
The agent receives the pre-computed inputs from Layer 1 plus the relevant evidence subset for this node. It evaluates the evidence in context and produces a structured finding. The agent does NOT decide which node to visit next. It does NOT query external systems. It answers one specific question per node.

**Layer 3 — Deterministic Decision Aggregation (computed after all nodes):**
The structured findings from all nodes are aggregated by deterministic rules to produce the final recommendation:
- All nodes clear → Close
- Any blocking finding → Immediate RFI targeting the specific gap
- Accumulated soft findings → Broader RFI or SAR depending on severity
- Strong findings + typology match → SAR

### Blocking vs. Accumulating Findings

Each node produces a finding with a `finding_type` field:

**Blocking:** The investigation cannot continue without additional information. This triggers an immediate exit from the graph with a targeted RFI. Example: unknown counterparty sending material amounts with no prior clearance, no declared relationship, and no plausible explanation.

**Accumulating:** Something is flagged but the investigation can proceed. The finding is carried in state to subsequent nodes and contributes to the full-picture assessment at the end. Example: credits moderately above declared income, known counterparty with higher-than-cleared volumes.

This distinction produces better RFIs:
- A blocking RFI is narrow and specific: "Please provide documentation of your relationship with Yao Zeng and the purpose of AED 306,500 received in 5 transactions."
- An accumulated RFI after full graph traversal is broader: "Please provide source of funds documentation for credits totaling AED 666k from four individuals, and clarify the nature of PURCHASE MONEY payments to your employer."

### Node Output Schema

Every node produces the same structured output:

```json
{
  "node": "node_1_kyc",
  "assessment": "inconsistent | consistent | partially_consistent",
  "finding_type": "blocking | accumulating | clear",
  "confidence": 0.92,
  "evidence_cited": [
    {
      "fact": "Total credits AED 665,882 against declared monthly income of AED 9,000",
      "source": "pre_computed_metrics.credits_to_declared_income_ratio",
      "significance": "74x declared income over 2-month period"
    }
  ],
  "narrative": "Customer's observed credit volumes are fundamentally inconsistent with declared employment income...",
  "investigative_context_for_downstream": "Customer is salaried retail — subsequent nodes should evaluate counterparty relationships as potential unexplained personal receipts, not business activity."
}
```

The `investigative_context_for_downstream` field is critical. This is how Node 1 shapes the rest of the investigation. It tells subsequent nodes what "unexplained" means for this customer.

---

## Node 1: KYC Consistency Check

### Question
Is the customer's observed activity consistent with their declared KYC profile?

### Pre-Computed Inputs (Layer 1)
- Credits-to-declared-income ratio (e.g., 74x)
- Total credits and debits for event period
- Customer risk rating
- PEP status and adverse media screening
- Account age / relationship length
- Triggered indicators list

### Evidence Available
- Full KYC profile (segment, business type, declared activity, declared income)
- Pre-computed metrics (all ratios and aggregates)
- Event vs. baseline comparisons

### What the AI Does

The AI's task is NOT just checking if credits exceed declared income. That ratio is pre-computed. The AI interprets what "consistent" means for this specific customer profile:

- **Salaried employee:** Income vs. credits is the primary dimension. A 74x ratio is unambiguous. But a 2x ratio might be explainable by savings, family transfers, or a declared side activity.
- **Self-employed / freelancer:** No fixed income to compare against. The AI evaluates historical volume trends, whether counterparties look like plausible clients, and whether amounts are consistent with the declared profession.
- **Company:** Authorized capital, declared business activity, and sector norms matter more than a simple income ratio. A trading company receiving large credits may be normal; the question is whether the counterparties and geographies align with the declared trade activity.
- **New customer (thin history):** Less baseline data to compare against. The AI factors in relationship age and flags cases where pattern establishment is too thin for reliable comparison.

The AI also assesses the weight of combined soft priors. A low-risk customer with no PEP status, no adverse media, but a 74x income ratio — the quantitative signal overwhelms the clean profile. A high-risk PEP customer with credits 1.5x income — the profile context elevates what would otherwise be a mild quantitative signal.

### Critical Output: Investigative Context

Node 1's most important output is the `investigative_context_for_downstream` field. This tells the rest of the graph how to frame the investigation:

- "Salaried retail customer — evaluate counterparty relationships as unexplained personal receipts"
- "Self-employed consultant — evaluate whether counterparties are plausible clients and amounts are consistent with consulting fees"
- "Import/export company — evaluate whether counterparties and geographies align with declared trade activity"
- "New customer, 7 months history — baseline comparison unreliable, weight analysis toward counterparty plausibility and flow patterns"

### Output
Finding type: Almost always **accumulating** (KYC inconsistency alone rarely blocks — it frames the investigation). The exception would be an extreme case like a sanctions hit or confirmed adverse media, which would be **blocking**.

---

## Node 2: Source of Funds / Source of Wealth

### Question
For each counterparty in the flagged transactions: is the source of funds adequately explained?

### Pre-Computed Inputs (Layer 1)
- Counterparty graph data (known/unknown, prior clearance, risk score, network connections)
- Compliance history (prior clearance conditions)

### Evidence Available
- All pulled credit transactions with counterparty details
- All pulled debit transactions with counterparty details
- Full counterparty graph for each counterparty (relationship profile, transaction aggregates, counterparty profile)
- Prior clearance conditions
- Node 1 finding and investigative context

### What the AI Does

The AI evaluates each counterparty against a hierarchy:

1. **Previously cleared counterparty, within clearance bounds:** Explained. No concern unless volumes exceed prior clearance threshold. If the prior clearance was for "$500k/quarter in metals trading" and current volume is $1.2M/quarter, flag the excess as accumulating.

2. **Previously cleared counterparty, exceeding clearance bounds:** The clearance covers the relationship but not the current volume. Accumulating finding — the relationship is known but the scale has changed.

3. **Known counterparty (in graph) but no prior clearance:** The system has seen this counterparty in transactions with other customers. The AI evaluates: are they a commercial entity with a known profile? Do they appear in other alerts or SARs? What's their risk score? This may be accumulating (known entity, no red flags) or blocking (known entity appearing in multiple SARs).

4. **Unknown counterparty, material amount:** This is the classic blocking scenario. No prior relationship, no clearance, no graph history, and a significant transfer. The investigation cannot determine legitimacy without additional information. Blocking finding — trigger RFI specifically requesting relationship documentation. (Materiality is configurable via `materiality_threshold`, default AED 50,000.)

5. **Unknown counterparty, immaterial amount:** Unknown but the amount is below the materiality threshold. Accumulating — note it but don't block the investigation.

The AI also evaluates the debit side. In the example case: funds debited to employer as "PURCHASE MONEY." The AI assesses whether the employer relationship explains the flow. Paying your employer is not inherently suspicious, but paying your employer 73x your salary in "PURCHASE MONEY" with no supporting documentation warrants investigation.

### Name-Based Entity Reasoning at This Node

The AI performs three name-similarity checks using the counterparty names and the customer's own name:

1. **Own-account detection:** Does any counterparty name closely match the customer's name? If so, the transaction may be a self-transfer between the customer's own accounts. Self-transfers combined with other flags (rapid movement, round amounts, new accounts) suggest layering. Self-transfers in isolation may be routine (e.g., moving between checking and savings).

2. **Counterparty consolidation:** Do any two counterparty names appear to be variants of the same person (e.g., "YAO ZENG" and "Y. ZENG", or "ZHIJUN YOU" and "ZHI JUN YOU")? If so, the true concentration to that individual is the sum across their accounts. What looks like moderate amounts from two counterparties may actually be a large amount from one.

3. **Related-person patterns:** Do counterparty names share family names or other patterns suggesting familial or organizational relationships? In the example case, all four credit counterparties have Chinese names — this doesn't mean they're related, but the AI should note the pattern and consider whether it's consistent with a specific typology (e.g., family pooling for property purchase, or coordinated funnel account).

The AI includes its name-similarity assessment in the finding narrative with a stated likelihood, not a binary determination. Example: "Counterparty YAO ZENG may be the same individual as Y. ZENG appearing in the customer's prior review (moderate likelihood). If confirmed, total exposure to this individual would be AED 450,000."

### Output
Finding type: **blocking** if any counterparty is unknown with material amounts and no plausible explanation. **Accumulating** if counterparties are partially known or volumes exceed clearance. **Clear** if all counterparties are explained.

When blocking: the output must include the specific counterparties and amounts that need RFI, so the system can generate a targeted information request.

---

## Node 3: Economic Justification

### Question
Does the flagged activity make economic sense given the customer's profile, counterparty context, and the investigative context from Node 1?

### Pre-Computed Inputs (Layer 1)
- Event vs. baseline comparisons across all dimensions
- Credit-to-debit ratio
- Flow pattern metrics (pass-through %, concentration on single counterparty)

### Evidence Available
- All pulled transactions with amounts, dates, counterparties, references
- Full counterparty graph with per-counterparty event-vs-baseline comparisons
- Event detection output (what changed and when)
- Indicator breach details (which dimensions breached)
- Node 1 finding (KYC context)
- Node 2 findings (counterparty status)

### What the AI Does

This is the most reasoning-intensive node. The AI connects the behavioral change (from event detection) to the customer context (from Node 1) and the counterparty picture (from Node 2) to determine whether the activity has a plausible economic explanation.

The AI considers:

**Flow pattern analysis:** In the example case, credits ≈ debits (98.7% pass-through). Four individuals send money in, nearly all of it goes to one entity. The AI recognizes this as a consolidation/forwarding pattern, not normal spending or saving behavior.

**Transaction reference interpretation:** "PURCHASE MONEY" to an employer that is a real estate company. The AI can hypothesize: are these individuals buying property through this company, using the customer's account as an intermediary? This is a plausible commercial explanation but also a classic funnel account pattern. The AI flags the ambiguity.

**Indicator-specific analysis:** If the triggered indicators were rapid movement and round amounts, the AI focuses on those dimensions. The rapid movement confirms the pass-through pattern. The round amounts suggest structured transfers rather than organic commercial payments.

**Prior clearance context:** If Node 2 found that a counterparty was cleared for a lower volume, the AI evaluates: is the increase consistent with business growth, or is it a step-change that suggests the prior clearance is being used as cover?

**Behavioral change narrative:** The event detection found a change. The AI articulates what changed and whether the change has a plausible explanation: "Transaction volumes increased 5x during the event period, coinciding with the appearance of 4 new counterparties not seen in the baseline period. No business or life event has been declared that would explain this shift."

### Output
Finding type: **accumulating**. Economic justification doesn't produce blocking findings — it produces assessments of whether the activity is justified, partially justified, or unjustified. This feeds into the typology matching and final decision.

The narrative here is critical. This is the core of the eventual SAR or RFI narrative — the explanation of why the activity is concerning.

---

## Node 4: Typology Matching

### Question
Does the accumulated evidence from Nodes 1–3 match a known money laundering, terrorism financing, or financial crime typology?

### Pre-Computed Inputs
- None additional — this node operates on the structured findings from Nodes 1–3

### Evidence Available
- All findings from Nodes 1–3 (structured outputs with narratives)
- Typology library (a reference document containing known typology definitions with their characteristic patterns)

### Typology Library

The typology library is a structured reference that the agent receives as context. Each typology includes:
- Name and description
- Characteristic patterns (what evidence combination indicates this typology)
- Regulatory references (which laws/regulations this typology relates to)
- Severity level

Example typologies relevant to the sample case:
- **Funnel/Collection Account:** Multiple unrelated individuals deposit funds into a single account, which consolidates and forwards them to a single beneficiary. Account holder has no apparent economic reason for the flows.
- **Layering through Real Estate:** Funds from multiple sources are channeled through real estate transactions to obscure their origin. Often involves over/under-invoicing of property.
- **Structuring:** Transactions deliberately kept below reporting thresholds or structured as round amounts to avoid detection.
- **Third-Party Pass-Through:** Account used as an intermediary for funds belonging to others, often with the account holder receiving a fee.

### What the AI Does

The AI performs narrative pattern matching: it reads the accumulated evidence and findings, reads the typology definitions, and determines which typologies the pattern fits. This is a semantic task — the AI matches the case narrative against typology descriptions, not boolean conditions.

The AI may identify:
- A strong match (evidence clearly fits a specific typology)
- A partial match (some elements fit but others are missing)
- Multiple potential matches (the pattern could be more than one typology)
- No match (the evidence is concerning but doesn't fit a known pattern)

### Output
Finding type: **accumulating**. Typology identification strengthens the case but doesn't by itself determine the outcome. The AI produces:
- Matched typology name(s) with confidence
- Which evidence from Nodes 1–3 maps to which typology characteristics
- Relevant regulatory references
- If no match: a statement that the pattern doesn't fit known typologies, which is also informative (novel pattern)

---

## Node 5: Decision Aggregation

### This Node Is Fully Deterministic — No AI

Node 5 collects the structured outputs from Nodes 1–4 and applies rules to produce the final recommendation. There is no AI reasoning here.

### Decision Rules

```
IF any node produced a blocking finding:
    → RFI targeting the specific blocking gap
    → (graph already exited at the blocking node, but decision is confirmed here)

IF no blocking findings AND all nodes are clear:
    → Close (with monitoring if any notes warrant it)

IF accumulated findings exist AND typology matched with high confidence:
    → SAR recommended
    → Cite specific typology and evidence

IF accumulated findings exist AND typology matched with partial confidence:
    → RFI recommended (gather more evidence before SAR determination)
    → Broader RFI covering all accumulated concerns

IF accumulated findings exist AND no typology match:
    → RFI recommended (concerning but pattern unclear)
    → RFI focused on unexplained aspects
```

### Output
Final recommendation: SAR / RFI / Close, with:
- Summary of all node findings
- Specific evidence supporting the recommendation
- If RFI: specific questions to ask and documents to request
- If SAR: typology reference and regulatory basis

---

## Stage 6: Report Generation

### What It Does
The AI generates a human-readable investigation report from the structured findings. This report is what the human reviewer sees.

### Report Structure
The report mirrors the decision graph. Each section corresponds to a node:

1. **Customer Profile Summary** — KYC data, account details, alert trigger information
2. **Event Summary** — What behavioral change was detected, event vs. baseline period
3. **KYC Assessment** — Node 1 finding with evidence
4. **Source of Funds Assessment** — Node 2 finding with counterparty-by-counterparty analysis
5. **Economic Justification Assessment** — Node 3 finding with flow analysis
6. **Typology Assessment** — Node 4 finding with typology match details
7. **Recommendation** — Node 5 output with supporting rationale

### Why AI for Report Generation

The report weaves evidence from across all nodes into a coherent investigative narrative. It's not a concatenation of node outputs — it's a synthesis that connects the KYC finding to the counterparty gaps to the flow pattern to the typology. This narrative coherence requires language generation. The structured node outputs ensure the report is grounded in evidence, while the AI provides readability.

---

## Graph Traversal and State Management

### LangGraph Implementation

The decision graph is implemented in LangGraph. The graph state carries:

```python
class ReviewState(TypedDict):
    case_json: dict              # Full case evidence from Stage 4
    node_findings: list[dict]    # Accumulated findings from each node
    current_node: str            # Which node is being evaluated
    investigative_context: str   # Set by Node 1, read by all subsequent nodes
    blocking_finding: bool       # Whether any node has produced a blocking finding
    blocking_details: dict       # If blocking: which node, which counterparty, what's needed
    final_recommendation: dict   # Set by Node 5
```

### Graph Flow

```
START
  ↓
Node 1 (KYC) → writes finding + investigative_context to state
  ↓
  [if blocking → exit to RFI output]
  ↓
Node 2 (SOF) → writes finding to state, reads investigative_context
  ↓
  [if blocking → exit to RFI output]
  ↓
Node 3 (Economic Justification) → writes finding to state
  ↓
  [always proceeds — no blocking possible here]
  ↓
Node 4 (Typology) → writes finding to state
  ↓
  [always proceeds]
  ↓
Node 5 (Decision Aggregation) → deterministic, writes final_recommendation
  ↓
Report Generation → produces narrative from all findings
  ↓
END
```

### Conditional Edges

After each AI node, a deterministic conditional edge checks the `finding_type` in the node's output:
- `blocking` → route to RFI output node (early exit)
- `accumulating` or `clear` → proceed to next node

The agent does NOT control routing. The graph controls routing based on structured outputs.

---

## Node Prompts — Implementation Guidance

Each node's AI call follows this structure:

```
SYSTEM: You are an AML compliance analyst evaluating a specific aspect 
of a flagged case. You will receive pre-computed metrics, case evidence, 
and findings from prior nodes. Produce a structured assessment.

You MUST output valid JSON matching the node output schema.
You MUST cite specific evidence for every claim.
You MUST NOT make assumptions about information not present in the evidence.
You MUST NOT query external systems.

ENTITY REASONING: Consider whether any counterparty names may refer to 
the same individual (name variants, transliterations, abbreviations), 
to the customer themselves (own-account transfers), or to related persons 
(shared family names, organizational patterns). If you identify potential 
name matches, note the likelihood and implications for your finding.

CONTEXT:
{investigative_context from Node 1, if this is Node 2+}

PRE-COMPUTED METRICS:
{relevant pre-computed values from case JSON}

EVIDENCE:
{relevant evidence subset for this node}

PRIOR FINDINGS:
{structured outputs from previous nodes, if any}

QUESTION:
{node-specific question}

Respond with a JSON object matching this schema:
{node output schema}
```

The prompt is the same structure for every node. What changes is:
- The specific question
- The evidence subset
- The prior findings available

This universality is by design. The investigation procedure is the same for every customer — the evidence differs, and the AI's interpretation adapts to the evidence. No SOP variants, no segment-specific prompts. The customer's profile is in the evidence, and the AI reasons about it.

---

## Configurable Parameters

The following values should be configurable in the implementation rather than hardcoded. Each parameter affects how the graph is built, how risk is computed, or how the AI interprets the data.

| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| score_lookback_months | 12 | 3–36 | Window for computing max risk score of internal counterparties. Longer = captures older spikes. Shorter = focuses on recent behavior. |
| lifetime_lookback_months | 12 | 3–60 | Window for computing lifetime transaction aggregates per relationship. Affects avg_monthly calculations and relationship characterization. |
| volume_spike_threshold | 2x | 1.5x–5x | Event-vs-baseline ratio above which is_volume_spike is set to true. Lower = more sensitive, more flags. Higher = fewer, stronger signals. |
| hub_threshold | 10 | 3–50 | Minimum connected_customer_count for is_hub = true. Depends on bank size and typical commercial entity connectivity. |
| dormancy_gap_months | 3 | 2–12 | Months of inactivity before a relationship is classified as dormant_reactivated (if transactions resume). |
| new_relationship_months | 3 | 1–12 | Relationships shorter than this are assigned activity_consistency = "new" regardless of transaction pattern. |
| materiality_threshold | 50,000 AED | 10k–500k | Amount below which an unknown counterparty is considered immaterial at Node 2. Affects blocking vs. accumulating finding decisions. |
| round_amount_pct_threshold | 50% | 20%–90% | Percentage of round-amount transactions above which the pattern is flagged. Affects Node 3 structuring assessment. |
| weighted_score_volume_window | 12 | 3–36 | Window (months) for computing transaction volumes used in external counterparty weighted average score calculation. |
| activity_regular_threshold | 70% | 50%–90% | Percentage of months active above which activity_consistency = "regular". Below this and above 30% = "intermittent". Below 30% = "burst". |

---

## The Medium-Risk Problem

The architecture specifically solves the medium-risk challenge:

**High-risk customers:** Score is high, evidence is usually obvious. A simpler system could handle these — assume RFI, document why.

**Low-risk customers:** Score is low, nothing to investigate. Close with standard monitoring.

**Medium-risk customers:** This is the majority of alert volume, and where the score alone can't decide. The indicators breach but the MEANING of those breaches requires contextual interpretation. The same flag pattern (4 new counterparties, rapid movement, round amounts) could be:
- A funnel account for money laundering
- An employee legitimately collecting payments from friends for a group property purchase through their employer
- A small business owner using a personal account for business (compliance violation, not criminality)

The flags are identical. The context determines the answer. This is exactly where the AI graph adds value — the deterministic stages identify THAT something changed and pull the relevant transactions, and the AI nodes interpret WHAT it means.

---

## Implementation Order

### Phase 1: Pipeline Foundation
1. Score time series storage and retrieval
2. Event detection algorithm (change-point detection)
3. Indicator computation (6 indicators, threshold configuration)
4. Transaction pulling logic (indicator → transaction mapping)

### Phase 2: Enrichment
5. Counterparty graph construction (edge properties, node properties, risk scores)
6. Counterparty graph update pipeline (daily aggregates, event-triggered updates)
7. Counterparty name inclusion in case JSON (enables AI-based entity reasoning at Node 2)
8. Compliance history aggregation
9. Case JSON assembly (full structure including counterparty graph section)

### Phase 3: Decision Graph
10. LangGraph graph structure with state management
11. Node 1 implementation (KYC) — start here, it's the foundation
12. Node 2 implementation (SOF) — heaviest consumer of counterparty graph
13. Node 3 implementation (Economic Justification)
14. Node 4 implementation (Typology Matching) — requires typology library
15. Node 5 implementation (Decision Aggregation rules)
16. Conditional edge routing logic

### Phase 4: Output
17. Report generation
18. RFI template generation (targeted and broad)
19. SAR narrative generation

### Phase 5: Evaluation
20. Run historical cases through the system
21. Compare system recommendations against actual analyst decisions
22. Tune prompts and thresholds based on divergence
23. Iterate until agreement rate meets target

---

## Appendix: Example Case Walkthrough

### Input: The Investigation Report

Customer: Chinese national, born 28 Nov 1977, employed at Nova Power Real Estate with monthly income of AED 9,000. Banking since 18 Jan 2024. Low risk rating.

Alerts triggered:
- Alert 2313401 (04 Aug 2025): Rapid movement of funds — credit turnover ≥ 163,000 and debit is +/-5% of credit (Credit: 200,000, Debit: 200,000)
- Alert 2308781 (02 Aug 2025): Round sum transactions = 7, aggregated amount = 700,000

Review period: 01 Jun 2025 to 03 Aug 2025

Credits: Received from 4 individuals (Yao Zeng AED 306,500 in 5 txns; Pengcheng Chang AED 150,000 in 3 txns; Zhijun You AED 102,000 in 2 txns; Jiansheng Sui AED 107,382.68 in 6 txns)

Debits: AED 657,510.95 to Nova Power Real Estate LLC (employer) in 8 txns, reference PURCHASE MONEY

Analyst recommendation: RFI

### What the System Would Produce

**Stage 3 output:** Triggered indicators = rapid_movement, round_amounts. Pulled transactions: all credit and debit transactions in the review period.

**Node 1 (KYC):** Assessment = inconsistent. Credits 74x declared monthly income. Salaried employee profile cannot explain volumes. Investigative context: "Retail salaried employee — evaluate counterparty relationships as unexplained personal receipts, not business activity."

**Node 2 (SOF):** Assessment = unexplained. All 4 credit counterparties are unknown individuals with no prior clearance. Yao Zeng is internal with max_score_12m = 0.85 (high risk) and 1 SAR — elevated concern. Pengcheng Chang and Zhijun You are external and new in event period. Finding type: blocking. Specific gap: relationship with all 4 individuals, particularly Yao Zeng given SAR history. Entity reasoning: all counterparties have Chinese names matching customer nationality — consistent with either family/community network or coordinated scheme; cannot determine without RFI.

**Node 3:** (Would not be reached if Node 2 blocks, but if the system proceeds) Assessment = unjustified. Pass-through pattern: 98.7% of credits forwarded to single entity. "PURCHASE MONEY" reference to employer is unexplained. Per-counterparty event-vs-baseline shows Yao Zeng at 3.6x baseline (volume spike), others entirely new. Pattern inconsistent with salaried employment.

**Node 4:** Pattern matches "Funnel/Collection Account" typology. Multiple unrelated individuals → consolidation → single beneficiary. Also partial match for "Third-Party Pass-Through" and "Layering through Real Estate" given the employer is a real estate company. Nova Power is a hub (47 connected customers) but low risk — likely legitimate commercial entity, though its role as both employer and sole debit recipient warrants scrutiny.

**Node 5:** Blocking finding at Node 2 → RFI recommended. Targeted questions: (1) Relationship with each of the 4 individuals. (2) Purpose of funds received. (3) Nature of "PURCHASE MONEY" payments to employer. (4) Supporting documentation for property transactions if applicable.

**The system reaches the same recommendation as the analyst (RFI) but with structured evidence, specific typology identification, counterparty risk context (Yao Zeng's high score and SAR history), and targeted questions that the original report did not provide.**
