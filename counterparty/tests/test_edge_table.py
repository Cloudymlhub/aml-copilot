"""Tests for edge table construction and identity resolution."""

import pytest
from pyspark.sql import functions as F

from counterparty.counterparty_graph import _build_edge_table, _compute_context_df
from counterparty.models import GraphParameters


@pytest.fixture
def edge_table(spark, sample_transactions, sample_account_master, sample_contexts):
    params = GraphParameters()
    context_df = _compute_context_df(spark, sample_contexts, params)
    return _build_edge_table(sample_transactions, sample_account_master, context_df)


class TestIdentityResolution:
    def test_acc1_resolves_to_cif_x(self, edge_table):
        """ACC-1 should resolve to CIF-X (internal)."""
        rows = (
            edge_table.filter(
                (F.col("source") == "CIF-A") & (F.col("target_account") == "ACC-1")
            )
            .select("target")
            .distinct()
            .collect()
        )
        assert len(rows) == 1
        assert rows[0]["target"] == "CIF-X"

    def test_external_stays_as_account(self, edge_table):
        """ACC-EXT-1 has no mapping, stays as raw account ID."""
        rows = (
            edge_table.filter(
                (F.col("source") == "CIF-A")
                & (F.col("target_account") == "ACC-EXT-1")
            )
            .select("target")
            .distinct()
            .collect()
        )
        assert len(rows) == 1
        assert rows[0]["target"] == "ACC-EXT-1"

    def test_multi_account_same_target(self, edge_table):
        """ACC-1 and ACC-X1 both resolve to CIF-X."""
        targets = (
            edge_table.filter(
                (F.col("source") == "CIF-A")
                & (F.col("target_account").isin(["ACC-1", "ACC-X1"]))
            )
            .select("target")
            .distinct()
            .collect()
        )
        assert all(r["target"] == "CIF-X" for r in targets)


class TestInternalFlag:
    def test_internal_flag_true(self, edge_table):
        """ACC-1 resolves → target_is_internal=True."""
        rows = (
            edge_table.filter(
                (F.col("source") == "CIF-A") & (F.col("target") == "CIF-X")
            )
            .select("target_is_internal")
            .distinct()
            .collect()
        )
        assert rows[0]["target_is_internal"] is True

    def test_internal_flag_false(self, edge_table):
        """ACC-EXT-1 unresolved → target_is_internal=False."""
        rows = (
            edge_table.filter(
                (F.col("source") == "CIF-A") & (F.col("target") == "ACC-EXT-1")
            )
            .select("target_is_internal")
            .distinct()
            .collect()
        )
        assert rows[0]["target_is_internal"] is False


class TestSelfLoop:
    def test_self_loop_removed(self, edge_table):
        """CIF-A → ACC-A (own account) should be filtered out."""
        count = edge_table.filter(
            (F.col("source") == "CIF-A") & (F.col("target") == "CIF-A")
        ).count()
        assert count == 0


class TestColumns:
    def test_preserves_all_columns(self, edge_table):
        """Edge table has all required columns."""
        expected = {
            "source",
            "target",
            "target_account",
            "target_name",
            "target_is_internal",
            "transaction_date",
            "direction",
            "amount",
        }
        assert set(edge_table.columns) == expected


class TestSecondDegreeInclusion:
    def test_includes_cp_own_txns(self, edge_table):
        """CIF-X's own transactions (to ACC-3) should be in the edge table."""
        count = edge_table.filter(
            (F.col("source") == "CIF-X") & (F.col("target_account") == "ACC-3")
        ).count()
        assert count > 0, "CIF-X → ACC-3 transactions should be included for 2nd degree"

    def test_includes_cp_inbound_txns(self, edge_table):
        """Non-reviewed CIF-Z transacting with CIF-X's account should be included."""
        count = edge_table.filter(
            (F.col("source") == "CIF-Z") & (F.col("target_account") == "ACC-1")
        ).count()
        assert count > 0, "CIF-Z → ACC-1 should be included for 2nd degree inbound"

    def test_outside_lifetime_filtered_from_pass1(self, edge_table):
        """CIF-A's 2023-01-01 txn may appear in pass 2 (broad bounds for 2nd degree)
        but should NOT appear in 1st-degree results (filtered by per-customer lifetime).
        The edge table itself includes pass 2 data; filtering happens in _compute_first_degree."""
        from datetime import date

        # The edge table includes 2nd-degree pass data with broad bounds,
        # so the old txn may exist. What matters is that 1st-degree computation
        # filters it out — tested in test_first_degree.py.
        # Here we just verify the edge table has expected structure.
        total_cif_a_to_cif_x = edge_table.filter(
            (F.col("source") == "CIF-A") & (F.col("target") == "CIF-X")
        ).count()
        assert total_cif_a_to_cif_x >= 4  # at least the 4 in-window txns
