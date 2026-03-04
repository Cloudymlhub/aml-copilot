"""
Pandas compute functions for counterparty graph construction.

Same function signatures as spark.py — called by graph.py when engine="pandas".
Expects pre-extracted data (via cache.read_pandas) rather than full tables.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

from ..models import (
    CaseContext,
    CustomerGraph,
    GraphParameters,
)
from .assemble import _assemble_from_rows

logger = logging.getLogger(__name__)


def _add_months(d: date, months: int) -> date:
    """Add months to a date (same helper as spark.py)."""
    from dateutil.relativedelta import relativedelta

    return d + relativedelta(months=months)


def _compute_context_df(
    contexts: List[CaseContext],
    params: GraphParameters,
) -> pd.DataFrame:
    """Compute per-customer date bounds from contexts + params."""
    rows = []
    for ctx in contexts:
        rd = ctx.review_date

        event_start = ctx.event_start or _add_months(rd, -params.default_event_months)
        event_end = ctx.event_end or rd
        baseline_start = ctx.baseline_start or _add_months(
            event_start, -params.default_baseline_months
        )
        baseline_end = ctx.baseline_end or _add_months(event_start, 0)

        rows.append(
            {
                "cif_no": ctx.cif_no,
                "review_date": rd,
                "event_start": event_start,
                "event_end": event_end,
                "baseline_start": baseline_start,
                "baseline_end": baseline_end,
                "lifetime_start": _add_months(rd, -params.lifetime_lookback_months),
                "network_start": _add_months(rd, -params.network_lookback_months),
                "rating_start": _add_months(rd, -params.rating_lookback_months),
            }
        )

    return pd.DataFrame(rows)


def _build_edge_table(
    txns: pd.DataFrame,
    account_master: pd.DataFrame,
    context_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build edge table from pre-extracted transactions.

    Unlike the Spark version, extraction already captured all 3 subsets
    (reviewed CIFs, cp CIFs, third-party inbound). So this function:
    1. Filters subset (a) per-customer lifetime windows
    2. Passes subsets (b) and (c) through (already date-scoped by extraction)
    3. Unions, deduplicates, resolves identities
    """
    reviewed_cifs = set(context_df["cif_no"])

    # Create account→CIF lookup
    acct_map = account_master.set_index("foracid")["cif_no"].to_dict()

    # --- Subset (a): Reviewed customers' edges (per-customer lifetime window) ---
    cust_txns = txns[txns["cif_no"].isin(reviewed_cifs)].copy()
    cust_txns = cust_txns.merge(
        context_df[["cif_no", "lifetime_start", "review_date"]], on="cif_no"
    )
    cust_txns = cust_txns[
        (cust_txns["transaction_date"] >= cust_txns["lifetime_start"])
        & (cust_txns["transaction_date"] <= cust_txns["review_date"])
    ]

    # Discover counterparty CIFs
    cp_accounts = set(cust_txns["counterparty_bank_account"].unique())
    cp_cifs = {acct_map[acc] for acc in cp_accounts if acc in acct_map}

    base_cols = [
        "cif_no",
        "counterparty_bank_account",
        "counterparty_name",
        "transaction_date",
        "direction",
        "amount",
    ]
    parts = [cust_txns[base_cols]]

    if cp_cifs:
        # --- Subset (b): CP CIFs' own transactions (already in extracted data) ---
        cp_own = txns[txns["cif_no"].isin(cp_cifs)][base_cols]
        parts.append(cp_own)

        # --- Subset (c): Third-party inbound to CP accounts ---
        cp_inbound = txns[
            txns["counterparty_bank_account"].isin(cp_accounts)
            & ~txns["cif_no"].isin(reviewed_cifs)
        ][base_cols]
        parts.append(cp_inbound)

        logger.debug(
            f"[edge_table/pd] {len(cp_accounts)} cp accounts, "
            f"{len(cp_cifs)} cp CIFs"
        )
    else:
        logger.debug("[edge_table/pd] No internal counterparties, skipping 2nd degree")

    all_txns = pd.concat(parts, ignore_index=True).drop_duplicates()

    # --- Resolve identities ---
    all_txns["_resolved_cif"] = all_txns["counterparty_bank_account"].map(acct_map)

    edges = pd.DataFrame(
        {
            "source": all_txns["cif_no"],
            "target": all_txns["_resolved_cif"].fillna(
                all_txns["counterparty_bank_account"]
            ),
            "target_account": all_txns["counterparty_bank_account"],
            "target_name": all_txns["counterparty_name"],
            "target_is_internal": all_txns["_resolved_cif"].notna(),
            "is_self_transfer": all_txns["cif_no"]
            == all_txns["_resolved_cif"].fillna(all_txns["counterparty_bank_account"]),
            "transaction_date": all_txns["transaction_date"],
            "direction": all_txns["direction"],
            "amount": all_txns["amount"],
        }
    )

    return edges


def _build_node_attributes(
    labels: Optional[pd.DataFrame],
    kyc: Optional[pd.DataFrame],
    edge_cifs: Set[str],
) -> Optional[pd.DataFrame]:
    """Static per-node attributes scoped to CIFs in the edge table."""
    if not edge_cifs:
        return None

    result = pd.DataFrame({"node_cif": list(edge_cifs)})

    if labels is not None:
        lab = labels[labels["cif_no"].isin(edge_cifs)].copy()
        has_alert = lab["alert_generated_date"].notna()
        is_l2 = lab["isL2"].fillna(False)
        is_sar = lab["isSAR"].fillna(False)
        is_open = is_l2 & lab["case_date_close"].isna()
        is_cleared = is_l2 & ~is_sar & lab["case_date_close"].notna()

        label_agg = (
            lab.assign(
                _alert=has_alert.astype(int),
                _case=is_l2.astype(int),
                _sar=is_sar.astype(int),
                _open=is_open,
                _cleared=is_cleared.astype(int),
                _clear_date=lab["case_date_close"].where(is_cleared),
            )
            .groupby("cif_no")
            .agg(
                node_alert_count=("_alert", "sum"),
                node_case_count=("_case", "sum"),
                node_sar_count=("_sar", "sum"),
                node_has_open_case=("_open", "max"),
                node_clearance_count=("_cleared", "sum"),
                node_last_clearance=("_clear_date", "max"),
            )
            .reset_index()
        )
        # Ensure bool type for node_has_open_case
        label_agg["node_has_open_case"] = label_agg["node_has_open_case"].fillna(
            False
        ).astype(bool)

        result = result.merge(
            label_agg.rename(columns={"cif_no": "node_cif"}), on="node_cif", how="left"
        )
    else:
        result["node_alert_count"] = 0
        result["node_case_count"] = 0
        result["node_sar_count"] = 0
        result["node_has_open_case"] = False
        result["node_clearance_count"] = 0
        result["node_last_clearance"] = None

    if kyc is not None:
        kyc_sub = kyc[kyc["cif_no"].isin(edge_cifs)][
            ["cif_no", "segment", "declared_income"]
        ].rename(
            columns={
                "cif_no": "node_cif",
                "segment": "node_segment",
                "declared_income": "node_declared_income",
            }
        )
        result = result.merge(kyc_sub, on="node_cif", how="left")
    else:
        result["node_segment"] = None
        result["node_declared_income"] = None

    return result


def _compute_first_degree(
    edges: pd.DataFrame,
    context_df: pd.DataFrame,
    params: GraphParameters,
    customer_cifs: Set[str],
) -> pd.DataFrame:
    """1st-degree metrics — pandas version."""
    # Filter to reviewed customers + join date bounds
    fd = edges[edges["source"].isin(customer_cifs)].merge(
        context_df.rename(columns={"cif_no": "source"}),
        on="source",
    )
    fd = fd[
        (fd["transaction_date"] >= fd["lifetime_start"])
        & (fd["transaction_date"] <= fd["review_date"])
    ]

    gk = ["source", "target", "target_is_internal"]

    # --- Relationship + Lifetime ---
    is_credit = fd["direction"] == "credit"
    is_debit = fd["direction"] == "debit"
    fd = fd.copy()
    fd["_ym"] = fd["transaction_date"].apply(lambda d: d.strftime("%Y-%m"))
    fd["_cr_amt"] = np.where(is_credit, fd["amount"], 0)
    fd["_dr_amt"] = np.where(is_debit, fd["amount"], 0)
    fd["_is_cr"] = is_credit.astype(int)
    fd["_is_dr"] = is_debit.astype(int)

    rel_lt = (
        fd.groupby(gk)
        .agg(
            first_txn_date=("transaction_date", "min"),
            last_txn_date=("transaction_date", "max"),
            months_active=("_ym", "nunique"),
            _has_cr=("_is_cr", "max"),
            _has_dr=("_is_dr", "max"),
            target_account=("target_account", "first"),
            target_name=("target_name", "first"),
            event_start=("event_start", "first"),
            event_end=("event_end", "first"),
            baseline_start=("baseline_start", "first"),
            baseline_end=("baseline_end", "first"),
            review_date=("review_date", "first"),
            lt_in_amt=("_cr_amt", "sum"),
            lt_in_count=("_is_cr", "sum"),
            lt_out_amt=("_dr_amt", "sum"),
            lt_out_count=("_is_dr", "sum"),
            lt_total_count=("amount", "count"),
        )
        .reset_index()
    )

    rel_lt["is_bidirectional"] = (rel_lt["_has_cr"] == 1) & (rel_lt["_has_dr"] == 1)
    rel_lt["is_new_in_event_period"] = rel_lt["first_txn_date"] >= rel_lt["event_start"]
    rel_lt["is_self_transfer"] = rel_lt["source"] == rel_lt["target"]
    rel_lt["lt_net"] = rel_lt["lt_in_amt"] - rel_lt["lt_out_amt"]
    rel_lt["lt_total_amt"] = rel_lt["lt_in_amt"] + rel_lt["lt_out_amt"]
    rel_lt = rel_lt.drop(columns=["_has_cr", "_has_dr"])

    # --- Event period ---
    ev = fd[
        (fd["transaction_date"] >= fd["event_start"])
        & (fd["transaction_date"] <= fd["event_end"])
    ].copy()
    ev["_round"] = (ev["amount"] % params.round_amount_modulo == 0).astype(int)

    if len(ev) > 0:
        event_df = (
            ev.groupby(gk)
            .agg(
                ev_in_amt=("_cr_amt", "sum"),
                ev_in_count=("_is_cr", "sum"),
                ev_out_amt=("_dr_amt", "sum"),
                ev_out_count=("_is_dr", "sum"),
                ev_round_count=("_round", "sum"),
            )
            .reset_index()
        )
    else:
        event_df = pd.DataFrame(columns=gk + [
            "ev_in_amt", "ev_in_count", "ev_out_amt", "ev_out_count", "ev_round_count"
        ])

    # --- Baseline period ---
    bl = fd[
        (fd["transaction_date"] >= fd["baseline_start"])
        & (fd["transaction_date"] <= fd["baseline_end"])
    ]

    if len(bl) > 0:
        baseline_df = (
            bl.groupby(gk)
            .agg(
                bl_in_amt=("_cr_amt", "sum"),
                bl_in_count=("_is_cr", "sum"),
                bl_out_amt=("_dr_amt", "sum"),
                bl_out_count=("_is_dr", "sum"),
            )
            .reset_index()
        )
    else:
        baseline_df = pd.DataFrame(columns=gk + [
            "bl_in_amt", "bl_in_count", "bl_out_amt", "bl_out_count"
        ])

    # Join
    result = rel_lt.merge(event_df, on=gk, how="left")
    result = result.merge(baseline_df, on=gk, how="left")

    # Fill nulls
    fill_cols = [
        "ev_in_amt", "ev_in_count", "ev_out_amt", "ev_out_count", "ev_round_count",
        "bl_in_amt", "bl_in_count", "bl_out_amt", "bl_out_count",
    ]
    result[fill_cols] = result[fill_cols].fillna(0)

    # Event vs baseline
    result["evb_in_change"] = np.where(
        result["bl_in_amt"] > 0,
        ((result["ev_in_amt"] - result["bl_in_amt"]) / result["bl_in_amt"]) * 100,
        None,
    )
    result["evb_out_change"] = np.where(
        result["bl_out_amt"] > 0,
        ((result["ev_out_amt"] - result["bl_out_amt"]) / result["bl_out_amt"]) * 100,
        None,
    )
    result["evb_is_spike"] = (
        result["ev_in_amt"] > result["bl_in_amt"] * params.volume_spike_threshold
    ) | (result["ev_out_amt"] > result["bl_out_amt"] * params.volume_spike_threshold)
    result["evb_is_new"] = (result["bl_in_count"] == 0) & (result["bl_out_count"] == 0)

    # Rename source → cif_no
    result = result.rename(columns={"source": "cif_no"})

    return result


def _compute_second_degree(
    edges: pd.DataFrame,
    nodes: Optional[pd.DataFrame],
    first_degree_df: pd.DataFrame,
    context_df: pd.DataFrame,
    risk_scores: Optional[pd.DataFrame],
    params: GraphParameters,
    skip_network: bool,
    skip_connected_compliance: bool,
) -> pd.DataFrame:
    """2nd-degree metrics — pandas version."""
    # Counterparty list with per-customer date bounds
    cp_list = (
        first_degree_df[["cif_no", "target", "target_is_internal"]]
        .drop_duplicates()
        .merge(
            context_df[["cif_no", "network_start", "review_date", "rating_start"]],
            on="cif_no",
        )
    )

    result = cp_list[["cif_no", "target", "target_is_internal"]].copy()
    all_connections = None

    # --- Network (hub detection) ---
    if not skip_network:
        # INBOUND: others transacting with this cp
        inbound = edges[["target", "source", "transaction_date"]].rename(
            columns={"target": "cp_id", "source": "connected_node"}
        )
        # OUTBOUND: cp's own transactions
        outbound = edges[["source", "target", "transaction_date"]].rename(
            columns={"source": "cp_id", "target": "connected_node"}
        )

        # Filter inbound by cp_list date bounds
        in_f = cp_list.merge(inbound, left_on="target", right_on="cp_id")
        in_f = in_f[
            (in_f["transaction_date"] >= in_f["network_start"])
            & (in_f["transaction_date"] <= in_f["review_date"])
        ][["cif_no", "target", "connected_node", "transaction_date"]]

        # Filter outbound (internal CPs only)
        out_cp = cp_list[cp_list["target_is_internal"]]
        out_f = out_cp.merge(outbound, left_on="target", right_on="cp_id")
        out_f = out_f[
            (out_f["transaction_date"] >= out_f["network_start"])
            & (out_f["transaction_date"] <= out_f["review_date"])
        ][["cif_no", "target", "connected_node", "transaction_date"]]

        all_connections = pd.concat([in_f, out_f], ignore_index=True)

        # Network metrics
        network_df = (
            all_connections.groupby(["cif_no", "target"])["connected_node"]
            .nunique()
            .reset_index()
            .rename(columns={"connected_node": "net_cust_count"})
        )
        network_df["net_is_hub"] = network_df["net_cust_count"] >= params.hub_threshold
        network_df["net_hub_score"] = np.where(
            network_df["net_cust_count"] >= params.hub_threshold,
            network_df["net_cust_count"] / params.hub_threshold,
            0.0,
        )

        result = result.merge(network_df, on=["cif_no", "target"], how="left")

        # --- Connected compliance ---
        if not skip_connected_compliance and nodes is not None:
            conn = all_connections.merge(
                nodes, left_on="connected_node", right_on="node_cif", how="left"
            )
            conn_agg = (
                conn.groupby(["cif_no", "target"])
                .agg(
                    cm_conn_alert=("node_alert_count", lambda x: x.fillna(0).sum()),
                    cm_conn_case=("node_case_count", lambda x: x.fillna(0).sum()),
                    cm_conn_sar=("node_sar_count", lambda x: x.fillna(0).sum()),
                    cm_conn_open=(
                        "node_has_open_case",
                        lambda x: int(x.astype(bool).sum()),
                    ),
                )
                .reset_index()
            )
            result = result.merge(conn_agg, on=["cif_no", "target"], how="left")

    # --- Own compliance (direct node lookup for internal CPs) ---
    if nodes is not None:
        own = nodes.rename(
            columns={
                "node_cif": "_oc_target",
                "node_alert_count": "cm_own_alert",
                "node_case_count": "cm_own_case",
                "node_sar_count": "cm_own_sar",
                "node_has_open_case": "cm_own_has_open",
                "node_clearance_count": "cm_own_clearance",
                "node_last_clearance": "cm_own_last_clear",
                "node_segment": "kyc_segment",
                "node_declared_income": "kyc_declared_income",
            }
        )
        # Only join for internal targets
        internal_mask = result["target_is_internal"]
        if internal_mask.any():
            internal_result = result[internal_mask].merge(
                own, left_on="target", right_on="_oc_target", how="left"
            ).drop(columns=["_oc_target"])
            external_result = result[~internal_mask]
            result = pd.concat([internal_result, external_result], ignore_index=True)

    # --- Risk scores ---
    if risk_scores is not None:
        # Internal CPs: direct score lookup
        internal_cp = cp_list[cp_list["target_is_internal"]]
        if len(internal_cp) > 0:
            sc = internal_cp.merge(
                risk_scores,
                left_on="target",
                right_on="cif_no",
                suffixes=("", "_rs"),
            )
            sc = sc[
                (sc["observation_date"] >= sc["rating_start"])
                & (sc["observation_date"] <= sc["review_date"])
            ]
            if len(sc) > 0:
                int_scores = (
                    sc.groupby(["cif_no", "target"])["score"]
                    .max()
                    .reset_index()
                    .rename(columns={"score": "sc_internal_max"})
                )
                int_scores["sc_internal_rating"] = np.where(
                    int_scores["sc_internal_max"] >= params.rating_high_threshold,
                    "high",
                    np.where(
                        int_scores["sc_internal_max"] >= params.rating_medium_threshold,
                        "medium",
                        "low",
                    ),
                )
                result = result.merge(
                    int_scores, on=["cif_no", "target"], how="left"
                )

        # External CPs: weighted avg of neighbors' scores
        if all_connections is not None and len(all_connections) > 0:
            ns = all_connections.merge(
                risk_scores.rename(columns={"cif_no": "_sc_cif"}),
                left_on="connected_node",
                right_on="_sc_cif",
            )
            ns = ns.merge(
                context_df[["cif_no", "rating_start", "review_date"]].rename(
                    columns={
                        "cif_no": "_ctx_cif",
                        "rating_start": "_rs",
                        "review_date": "_rd",
                    }
                ),
                left_on="cif_no",
                right_on="_ctx_cif",
            )
            ns = ns[(ns["observation_date"] >= ns["_rs"]) & (ns["observation_date"] <= ns["_rd"])]
            if len(ns) > 0:
                ext_scores = (
                    ns.groupby(["cif_no", "target"])["score"]
                    .mean()
                    .reset_index()
                    .rename(columns={"score": "sc_external_weighted_avg"})
                )
                result = result.merge(
                    ext_scores, on=["cif_no", "target"], how="left"
                )

    return result


def _assemble(
    first_degree_df: pd.DataFrame,
    second_degree_df: pd.DataFrame,
    nodes: Optional[pd.DataFrame],
    contexts: List[CaseContext],
    params: GraphParameters,
) -> Dict[str, CustomerGraph]:
    """Join first + second degree, convert to dicts, build output objects."""
    joined = first_degree_df.merge(
        second_degree_df, on=["cif_no", "target", "target_is_internal"], how="left"
    )

    rows = joined.to_dict("records")
    node_rows = nodes.to_dict("records") if nodes is not None else []

    return _assemble_from_rows(rows, node_rows, contexts, params)
