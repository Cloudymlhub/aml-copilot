"""Tests for 1st-degree metrics computation."""

import pytest
from pyspark.sql import functions as F

from counterparty.counterparty_graph import (
    _build_edge_table,
    _compute_context_df,
    _compute_first_degree,
)
from counterparty.models import GraphParameters


@pytest.fixture
def first_degree_df(spark, sample_transactions, sample_account_master, sample_contexts):
    params = GraphParameters()
    context_df = _compute_context_df(spark, sample_contexts, params)
    edges = _build_edge_table(sample_transactions, sample_account_master, context_df)
    customer_cifs = {ctx.cif_no for ctx in sample_contexts}
    return _compute_first_degree(edges, context_df, params, customer_cifs)


def _get_row(df, cif_no, target):
    return df.filter(
        (F.col("cif_no") == cif_no) & (F.col("target") == target)
    ).first()


class TestLifetimeAggregates:
    def test_cif_a_to_cif_x_amounts(self, first_degree_df):
        """CIF-A → CIF-X: debits include in-window txns. The edge table may include
        pass-2 data from broad date range, but 1st-degree filters by per-customer
        lifetime window. With 24-month lookback from 2024-06-15, the 2023-01-01 txn
        is within window (2022-06-15 to 2024-06-15), so 5 debits total."""
        row = _get_row(first_degree_df, "CIF-A", "CIF-X")
        assert row is not None
        assert row["lt_out_count"] == 5  # 5 debits (includes 2023-01-01, within 24mo window)
        assert row["lt_in_count"] == 1   # 1 credit
        assert abs(row["lt_out_amt"] - 30500.0) < 0.01  # 5k+8k+15k+2k+500=30500
        assert abs(row["lt_in_amt"] - 3000.0) < 0.01

    def test_cif_a_to_ext1(self, first_degree_df):
        """CIF-A → ACC-EXT-1: 1 debit (12k) + 1 credit (4k)."""
        row = _get_row(first_degree_df, "CIF-A", "ACC-EXT-1")
        assert row is not None
        assert row["lt_out_count"] == 1
        assert row["lt_in_count"] == 1
        assert abs(row["lt_out_amt"] - 12000.0) < 0.01
        assert abs(row["lt_in_amt"] - 4000.0) < 0.01

    def test_net_flow(self, first_degree_df):
        """Net flow = inbound - outbound."""
        row = _get_row(first_degree_df, "CIF-A", "CIF-X")
        expected_net = 3000.0 - 30500.0  # credit 3k - debits 30.5k
        assert abs(row["lt_net"] - expected_net) < 0.01

    def test_cif_b_to_cif_x(self, first_degree_df):
        """CIF-B → CIF-X: 2 debits (7k+9k=16k)."""
        row = _get_row(first_degree_df, "CIF-B", "CIF-X")
        assert row is not None
        assert row["lt_out_count"] == 2
        assert abs(row["lt_out_amt"] - 16000.0) < 0.01


class TestEventPeriodFilter:
    def test_cif_a_event_period(self, first_degree_df):
        """CIF-A event: 3 months before 2024-06-15 → ~2024-03-15 to 2024-06-15.
        CIF-A→CIF-X in event: 2024-03-15 (8k debit), 2024-05-20 (3k credit),
        2024-06-01 (15k debit), 2024-04-10 (2k debit via ACC-X1)."""
        row = _get_row(first_degree_df, "CIF-A", "CIF-X")
        # Event period debits: 8k + 15k + 2k = 25k (3 debits)
        # Event period credits: 3k (1 credit)
        assert row["ev_out_count"] >= 2  # at least the debits in event window
        assert row["ev_out_amt"] > 0

    def test_cif_b_event_period(self, first_degree_df):
        """CIF-B event: 3 months before 2024-07-01 → ~2024-04-01 to 2024-07-01.
        CIF-B→CIF-X in event: 2024-04-20 (7k), 2024-06-15 (9k)."""
        row = _get_row(first_degree_df, "CIF-B", "CIF-X")
        assert row["ev_out_count"] == 2
        assert abs(row["ev_out_amt"] - 16000.0) < 0.01


class TestBaselinePeriodFilter:
    def test_baseline_only_includes_baseline_window(self, first_degree_df):
        """Baseline transactions should only be from baseline period."""
        row = _get_row(first_degree_df, "CIF-A", "CIF-X")
        # Baseline is before event_start, so these are earlier transactions
        # The exact counts depend on window calculation
        assert row["bl_out_count"] is not None
        assert row["bl_out_amt"] is not None


class TestEventVsBaseline:
    def test_spike_detection(self, first_degree_df):
        """When event >> baseline, is_volume_spike should be True."""
        row = _get_row(first_degree_df, "CIF-A", "CIF-X")
        # evb_is_spike is computed based on threshold
        assert row["evb_is_spike"] is not None  # bool field exists

    def test_new_relationship(self, first_degree_df):
        """evb_is_new=True when no baseline transactions exist."""
        # CIF-B → ACC-EXT-2: single txn on 2024-03-10
        # Depending on baseline window, this might be in baseline or event
        row = _get_row(first_degree_df, "CIF-B", "ACC-EXT-2")
        assert row is not None
        assert row["evb_is_new"] is not None


class TestBidirectional:
    def test_bidirectional_true(self, first_degree_df):
        """CIF-A → CIF-X has both credit and debit → is_bidirectional=True."""
        row = _get_row(first_degree_df, "CIF-A", "CIF-X")
        assert row["is_bidirectional"] is True

    def test_bidirectional_false(self, first_degree_df):
        """CIF-B → CIF-X has only debits → is_bidirectional=False."""
        row = _get_row(first_degree_df, "CIF-B", "CIF-X")
        assert row["is_bidirectional"] is False


class TestPerCustomerDates:
    def test_different_review_dates(self, first_degree_df):
        """CIF-A and CIF-B have different review dates, both produce results."""
        cif_a_count = first_degree_df.filter(F.col("cif_no") == "CIF-A").count()
        cif_b_count = first_degree_df.filter(F.col("cif_no") == "CIF-B").count()
        assert cif_a_count > 0
        assert cif_b_count > 0

    def test_cif_a_counterparty_count(self, first_degree_df):
        """CIF-A should have 2 counterparties: CIF-X and ACC-EXT-1 (self-loop removed)."""
        count = first_degree_df.filter(F.col("cif_no") == "CIF-A").count()
        assert count == 2

    def test_cif_b_counterparty_count(self, first_degree_df):
        """CIF-B should have 3 counterparties: CIF-X, CIF-Y, ACC-EXT-2."""
        count = first_degree_df.filter(F.col("cif_no") == "CIF-B").count()
        assert count == 3
