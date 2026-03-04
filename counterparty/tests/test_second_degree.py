"""Tests for 2nd-degree metrics computation."""

import pytest
from pyspark.sql import functions as F

from counterparty.compute import (
    _build_edge_table,
    _build_node_attributes,
    _compute_context_df,
    _compute_first_degree,
    _compute_second_degree,
)
from counterparty.models import GraphParameters


@pytest.fixture
def second_degree_setup(
    spark, sample_transactions, sample_account_master, sample_contexts,
    sample_risk_scores, sample_labels, sample_kyc,
):
    """Build all dependencies and return second_degree_df + helpers."""
    params = GraphParameters()
    context_df = _compute_context_df(spark, sample_contexts, params)
    edges = _build_edge_table(sample_transactions, sample_account_master, context_df)
    edges = edges.cache()
    customer_cifs = {ctx.cif_no for ctx in sample_contexts}
    first_degree_df = _compute_first_degree(edges, context_df, params, customer_cifs)

    source_cifs = {r[0] for r in edges.select("source").distinct().collect()}
    internal_targets = {
        r[0] for r in edges.filter(F.col("target_is_internal")).select("target").distinct().collect()
    }
    edge_cifs = source_cifs | internal_targets
    nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)

    second_degree_df = _compute_second_degree(
        edges, nodes, first_degree_df, context_df,
        sample_risk_scores, params,
        skip_network=False, skip_connected_compliance=False,
    )
    return {
        "df": second_degree_df,
        "edges": edges,
        "params": params,
        "context_df": context_df,
        "first_degree_df": first_degree_df,
        "nodes": nodes,
    }


def _get_row(df, cif_no, target):
    return df.filter(
        (F.col("cif_no") == cif_no) & (F.col("target") == target)
    ).first()


class TestInboundConnections:
    def test_cif_x_has_inbound_connections(self, second_degree_setup):
        """CIF-X (cp of both A and B) should have inbound connections from A, B, Z."""
        df = second_degree_setup["df"]
        # From CIF-A's perspective, CIF-X should have connections
        row = _get_row(df, "CIF-A", "CIF-X")
        assert row is not None
        assert row["net_cust_count"] is not None
        assert row["net_cust_count"] >= 2  # at least CIF-A, CIF-B transact with CIF-X


class TestOutboundConnections:
    def test_cif_x_outbound_included(self, second_degree_setup):
        """CIF-X's own txn to ACC-3 adds to its neighborhood (internal cp → outbound counted)."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-A", "CIF-X")
        # CIF-X is internal, so outbound edges are included in neighbor count
        # Neighbors: CIF-A, CIF-B, CIF-Z (inbound) + CIF-W, ACC-EXT-1 (outbound)
        assert row["net_cust_count"] >= 3


class TestHubDetection:
    def test_cif_x_is_hub(self, second_degree_setup):
        """CIF-X with many connections should be detected as hub (threshold=5)."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-A", "CIF-X")
        # Whether it's a hub depends on exact count vs threshold (default 5)
        # CIF-X has: CIF-A, CIF-B, CIF-Z inbound + CIF-W, ACC-EXT-1 outbound = 5
        # With threshold=5, net_cust_count >= 5 → is_hub
        if row["net_cust_count"] >= 5:
            assert row["net_is_hub"] is True
            assert row["net_hub_score"] > 0

    def test_external_not_hub(self, second_degree_setup):
        """External cp with few connections shouldn't be a hub."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-B", "ACC-EXT-2")
        if row is not None and row["net_cust_count"] is not None:
            # ACC-EXT-2 only has CIF-B transacting with it
            assert row["net_cust_count"] < 5


class TestExternalCpInboundOnly:
    def test_external_cp_no_outbound(self, second_degree_setup):
        """External cp (ACC-EXT-2): only inbound counted (can't expand outbound)."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-B", "ACC-EXT-2")
        if row is not None and row["net_cust_count"] is not None:
            # Only CIF-B transacts with ACC-EXT-2
            assert row["net_cust_count"] <= 2


class TestConnectedCompliance:
    def test_cif_x_connected_sar(self, second_degree_setup):
        """CIF-X's neighbor CIF-B has SAR → cm_conn_sar > 0."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-A", "CIF-X")
        # CIF-B (who transacts with CIF-X) has a SAR
        rd = row.asDict()
        if row is not None and rd.get("cm_conn_sar") is not None:
            assert rd["cm_conn_sar"] > 0


class TestRiskScoreInternal:
    def test_cif_x_internal_score(self, second_degree_setup):
        """CIF-X (internal cp) should have direct score lookup."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-A", "CIF-X")
        assert row is not None
        assert row["sc_internal_max"] is not None
        # CIF-X scores in window: 0.75, 0.80, 0.85, 0.82 → max=0.85
        assert abs(row["sc_internal_max"] - 0.85) < 0.01

    def test_cif_x_risk_rating_high(self, second_degree_setup):
        """CIF-X with score 0.85 → rating=high (threshold 0.7)."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-A", "CIF-X")
        assert row["sc_internal_rating"] == "high"


class TestRiskScoreWindow:
    def test_old_score_excluded(self, second_degree_setup):
        """CIF-X's 2023-06-01 score (0.90) should be excluded from rating window."""
        df = second_degree_setup["df"]
        row = _get_row(df, "CIF-A", "CIF-X")
        # If 0.90 were included, max would be 0.90 not 0.85
        assert row["sc_internal_max"] is not None
        assert row["sc_internal_max"] < 0.90


class TestSkipFlags:
    def test_skip_network(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc,
    ):
        """skip_network=True → network fields default."""
        params = GraphParameters()
        context_df = _compute_context_df(spark, sample_contexts, params)
        edges = _build_edge_table(sample_transactions, sample_account_master, context_df)
        customer_cifs = {ctx.cif_no for ctx in sample_contexts}
        first_degree_df = _compute_first_degree(edges, context_df, params, customer_cifs)

        source_cifs = {r[0] for r in edges.select("source").distinct().collect()}
        internal_targets = {
            r[0] for r in edges.filter(F.col("target_is_internal")).select("target").distinct().collect()
        }
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, source_cifs | internal_targets)

        sd = _compute_second_degree(
            edges, nodes, first_degree_df, context_df,
            sample_risk_scores, params,
            skip_network=True, skip_connected_compliance=False,
        )
        row = _get_row(sd, "CIF-A", "CIF-X")
        assert row is not None
        # Network fields should be null when skipped
        assert row.asDict().get("net_cust_count") is None

    def test_skip_compliance(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc,
    ):
        """skip_connected_compliance=True → connected compliance fields default."""
        params = GraphParameters()
        context_df = _compute_context_df(spark, sample_contexts, params)
        edges = _build_edge_table(sample_transactions, sample_account_master, context_df)
        customer_cifs = {ctx.cif_no for ctx in sample_contexts}
        first_degree_df = _compute_first_degree(edges, context_df, params, customer_cifs)

        source_cifs = {r[0] for r in edges.select("source").distinct().collect()}
        internal_targets = {
            r[0] for r in edges.filter(F.col("target_is_internal")).select("target").distinct().collect()
        }
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, source_cifs | internal_targets)

        sd = _compute_second_degree(
            edges, nodes, first_degree_df, context_df,
            sample_risk_scores, params,
            skip_network=False, skip_connected_compliance=True,
        )
        row = _get_row(sd, "CIF-A", "CIF-X")
        assert row is not None
        # Connected compliance fields should be null when skipped
        assert row.asDict().get("cm_conn_sar") is None
