"""Integration tests for the full CounterpartyGraph pipeline."""

import json
import os
import tempfile

import pytest

from counterparty.graph import CounterpartyGraph
from counterparty.models import (
    CaseContext,
    CustomerGraph,
    CustomerProfile,
    CustomerSummary,
    GraphParameters,
)


@pytest.fixture
def graph(
    spark, sample_transactions, sample_account_master, sample_contexts,
    sample_risk_scores, sample_labels, sample_kyc,
):
    return CounterpartyGraph(
        spark, sample_transactions, sample_account_master, sample_contexts,
        risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
    )


class TestFullPipeline:
    def test_results_available(self, graph):
        """Results are immediately available after construction."""
        assert len(graph.results) > 0

    def test_both_customers_present(self, graph):
        """Both CIF-A and CIF-B should be in results."""
        assert "CIF-A" in graph.results
        assert "CIF-B" in graph.results


class TestResultStructure:
    def test_result_type(self, graph):
        """Output is Dict[str, CustomerGraph]."""
        for cif, cg in graph.results.items():
            assert isinstance(cif, str)
            assert isinstance(cg, CustomerGraph)

    def test_customer_graph_has_profile(self, graph):
        """Each CustomerGraph has a profile."""
        cg = graph.results["CIF-A"]
        assert isinstance(cg.profile, CustomerProfile)
        assert cg.profile.cif_no == "CIF-A"

    def test_customer_graph_has_summary(self, graph):
        """Each CustomerGraph has summary stats."""
        cg = graph.results["CIF-A"]
        assert isinstance(cg.summary, CustomerSummary)


class TestCustomerProfile:
    def test_profile_segment(self, graph):
        """CIF-A profile should have segment from KYC."""
        profile = graph.results["CIF-A"].profile
        assert profile.segment == "sme"

    def test_profile_compliance(self, graph):
        """CIF-A has 1 alert."""
        profile = graph.results["CIF-A"].profile
        assert profile.alert_count == 1


class TestCounterpartiesKeyedByTarget:
    def test_keyed_by_target_id(self, graph):
        """Counterparties should be keyed by resolved target ID."""
        cps = graph.results["CIF-A"].counterparties
        assert "CIF-X" in cps  # resolved ID, not ACC-1
        assert "ACC-EXT-1" in cps  # external stays as account

    def test_unique_keys(self, graph):
        """Each target appears once (multi-account merged)."""
        cps = graph.results["CIF-A"].counterparties
        # ACC-1 and ACC-X1 both resolve to CIF-X → single entry
        assert len([k for k in cps if k == "CIF-X"]) == 1


class TestCustomerSummary:
    def test_cif_a_counts(self, graph):
        """CIF-A: 3 counterparties (CIF-X internal, ACC-EXT-1 external, CIF-A self-transfer)."""
        s = graph.results["CIF-A"].summary
        assert s.total_counterparties == 3
        assert s.internal_count == 2  # CIF-X + self (CIF-A resolves as internal)
        assert s.external_count == 1

    def test_cif_b_counts(self, graph):
        """CIF-B: 3 counterparties (CIF-X, CIF-Y internal; ACC-EXT-2 external)."""
        s = graph.results["CIF-B"].summary
        assert s.total_counterparties == 3
        assert s.internal_count == 2
        assert s.external_count == 1


class TestEventPeriodsDict:
    def test_event_periods_has_event_key(self, graph):
        """event_periods should have 'event' key."""
        cp = graph.results["CIF-A"].counterparties["CIF-X"]
        assert "event" in cp.event_periods

    def test_event_vs_baselines_has_event_key(self, graph):
        """event_vs_baselines should have 'event' key."""
        cp = graph.results["CIF-A"].counterparties["CIF-X"]
        assert "event" in cp.event_vs_baselines


class TestInternalVsExternalProfile:
    def test_internal_has_internal_profile(self, graph):
        """Internal cp should have InternalProfile set."""
        cp = graph.results["CIF-A"].counterparties["CIF-X"]
        assert cp.target_is_internal is True
        assert cp.internal_profile is not None
        assert cp.external_profile is None

    def test_external_has_external_profile(self, graph):
        """External cp should have ExternalProfile set."""
        cp = graph.results["CIF-A"].counterparties["ACC-EXT-1"]
        assert cp.target_is_internal is False
        assert cp.external_profile is not None


class TestSelfTransfer:
    def test_self_transfer_in_results(self, graph):
        """CIF-A → ACC-A (own account) should appear as counterparty with is_self_transfer=True."""
        cps = graph.results["CIF-A"].counterparties
        assert "CIF-A" in cps
        assert cps["CIF-A"].is_self_transfer is True

    def test_non_self_transfer(self, graph):
        """Normal counterparties have is_self_transfer=False."""
        cp_internal = graph.results["CIF-A"].counterparties["CIF-X"]
        assert cp_internal.is_self_transfer is False
        cp_external = graph.results["CIF-A"].counterparties["ACC-EXT-1"]
        assert cp_external.is_self_transfer is False


class TestEmptyContexts:
    def test_empty_contexts(self, spark, sample_transactions, sample_account_master):
        """Empty contexts → empty results, no crash."""
        g = CounterpartyGraph(
            spark, sample_transactions, sample_account_master, [],
        )
        assert g.results == {}
        assert g.edge_count == 0
        assert g.node_count == 0


class TestGraphProperties:
    def test_edge_count(self, graph):
        """edge_count returns positive integer."""
        assert graph.edge_count > 0

    def test_node_count(self, graph):
        """node_count returns positive integer."""
        assert graph.node_count > 0

    def test_internal_ratio(self, graph):
        """internal_ratio is between 0 and 1."""
        ratio = graph.internal_ratio
        assert 0.0 <= ratio <= 1.0


class TestBatchMetrics:
    def test_metrics_customers(self, graph):
        """Metrics has correct customer count."""
        assert graph.metrics.total_customers == 2

    def test_metrics_timing(self, graph):
        """Metrics has compute time."""
        assert graph.metrics.compute_time_seconds > 0

    def test_metrics_step_times(self, graph):
        """Step times are populated."""
        assert len(graph.metrics.step_times) > 0
        assert "edge_table" in graph.metrics.step_times

    def test_metrics_to_dict(self, graph):
        """to_dict() returns serializable dict."""
        d = graph.metrics.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # should not raise


class TestSaveAndLoad:
    def test_round_trip(self, spark, graph):
        """save → load preserves results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_graph")
            graph.save(path)

            # Verify files exist
            assert os.path.exists(os.path.join(path, "results.json"))
            assert os.path.exists(os.path.join(path, "metadata.json"))

            # Load and verify
            loaded = CounterpartyGraph.load(spark, path)
            assert len(loaded.results) == len(graph.results)
            assert "CIF-A" in loaded.results
            assert "CIF-B" in loaded.results

            # Verify counterparty data preserved
            orig_cp = graph.results["CIF-A"].counterparties["CIF-X"]
            loaded_cp = loaded.results["CIF-A"].counterparties["CIF-X"]
            assert orig_cp.counterparty_name == loaded_cp.counterparty_name
            assert orig_cp.target_is_internal == loaded_cp.target_is_internal

    def test_metadata_json(self, graph):
        """metadata.json has edge_count, node_count, timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_graph")
            graph.save(path)

            with open(os.path.join(path, "metadata.json")) as f:
                meta = json.load(f)
            assert "edge_count" in meta
            assert "node_count" in meta
            assert "timestamp" in meta
            assert "metrics" in meta
            assert "params" in meta


class TestCache:
    def test_cache_creates_parquet_files(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc,
    ):
        """Caching saves intermediate DataFrames as parquet files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            g = CounterpartyGraph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
                cache_path=tmpdir, batch_id="test_batch",
            )
            cache_dir = os.path.join(tmpdir, "test_batch")
            assert os.path.exists(cache_dir)
            # At least edge_table and first_degree should be cached
            cached_files = os.listdir(cache_dir)
            parquet_dirs = [f for f in cached_files if f.endswith(".parquet")]
            assert len(parquet_dirs) >= 2
            assert "CIF-A" in g.results

    def test_cache_reuse(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc,
    ):
        """Second run with same batch_id uses cached data and produces same results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            g1 = CounterpartyGraph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
                cache_path=tmpdir, batch_id="reuse_test",
            )
            g2 = CounterpartyGraph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
                cache_path=tmpdir, batch_id="reuse_test",
            )
            assert len(g1.results) == len(g2.results)
            assert set(g1.results.keys()) == set(g2.results.keys())

    def test_overwrite_cache(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc,
    ):
        """overwrite_cache=True rewrites cached data without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            CounterpartyGraph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
                cache_path=tmpdir, batch_id="overwrite_test",
            )
            # Second run with overwrite should not raise
            g2 = CounterpartyGraph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
                cache_path=tmpdir, batch_id="overwrite_test",
                overwrite_cache=True,
            )
            assert "CIF-A" in g2.results

    def test_no_cache_by_default(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc,
    ):
        """Without cache_path/batch_id, no files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            CounterpartyGraph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
            )
            # tmpdir should be empty (no cache files)
            assert len(os.listdir(tmpdir)) == 0


class TestGetCustomer:
    def test_found(self, graph):
        """Returns CustomerGraph for known CIF."""
        cg = graph.get_customer("CIF-A")
        assert cg is not None
        assert isinstance(cg, CustomerGraph)
        assert cg.profile.cif_no == "CIF-A"

    def test_not_found(self, graph):
        """Returns None for unknown CIF."""
        assert graph.get_customer("CIF-UNKNOWN") is None


class TestGetNode:
    def test_get_node_raw(self, graph):
        """get_node() returns attrs + edges from raw graph."""
        node = graph.get_node("CIF-A")
        assert node is not None
        assert "node_attrs" in node
        assert "counterparties" in node
        assert len(node["counterparties"]) > 0

    def test_get_node_unknown(self, graph):
        """get_node() for unknown CIF returns empty counterparties."""
        node = graph.get_node("CIF-NONEXISTENT")
        assert node is not None
        assert len(node["counterparties"]) == 0
