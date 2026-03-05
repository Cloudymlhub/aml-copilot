"""Integration tests for the full CounterpartyGraph pipeline."""

import json
import os
import tempfile

import pytest

from counterparty.graph import create_counterparty_graph, load_counterparty_graph
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
    return create_counterparty_graph(
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
        g = create_counterparty_graph(
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
            loaded = load_counterparty_graph(spark, path)
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
            g = create_counterparty_graph(
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
            g1 = create_counterparty_graph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
                cache_path=tmpdir, batch_id="reuse_test",
            )
            g2 = create_counterparty_graph(
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
            create_counterparty_graph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
                cache_path=tmpdir, batch_id="overwrite_test",
            )
            # Second run with overwrite should not raise
            g2 = create_counterparty_graph(
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
            create_counterparty_graph(
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


# =============================================================================
# PANDAS ENGINE TESTS
# =============================================================================


@pytest.fixture
def pandas_graph(
    spark, sample_transactions, sample_account_master, sample_contexts,
    sample_risk_scores, sample_labels, sample_kyc, tmp_path,
):
    return create_counterparty_graph(
        spark, sample_transactions, sample_account_master, sample_contexts,
        risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
        engine="pandas", cache_path=str(tmp_path), batch_id="pd_test",
    )


class TestPandasEngine:
    """Pandas engine produces same results as Spark."""

    def test_requires_cache(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
    ):
        """engine='pandas' without cache raises ValueError."""
        with pytest.raises(ValueError, match="requires cache_path"):
            create_counterparty_graph(
                spark, sample_transactions, sample_account_master, sample_contexts,
                engine="pandas",
            )

    def test_both_customers_present(self, pandas_graph):
        assert "CIF-A" in pandas_graph.results
        assert "CIF-B" in pandas_graph.results

    def test_same_counterparty_counts(self, graph, pandas_graph):
        """Pandas engine produces same counterparty counts as Spark."""
        for cif in ["CIF-A", "CIF-B"]:
            spark_s = graph.results[cif].summary
            pd_s = pandas_graph.results[cif].summary
            assert spark_s.total_counterparties == pd_s.total_counterparties, (
                f"{cif}: total {spark_s.total_counterparties} vs {pd_s.total_counterparties}"
            )
            assert spark_s.internal_count == pd_s.internal_count, (
                f"{cif}: internal {spark_s.internal_count} vs {pd_s.internal_count}"
            )
            assert spark_s.external_count == pd_s.external_count, (
                f"{cif}: external {spark_s.external_count} vs {pd_s.external_count}"
            )

    def test_same_counterparty_keys(self, graph, pandas_graph):
        """Both engines discover the same counterparties."""
        for cif in ["CIF-A", "CIF-B"]:
            spark_keys = set(graph.results[cif].counterparties.keys())
            pd_keys = set(pandas_graph.results[cif].counterparties.keys())
            assert spark_keys == pd_keys, f"{cif}: {spark_keys} vs {pd_keys}"

    def test_same_lifetime_amounts(self, graph, pandas_graph):
        """Lifetime transaction amounts match between engines."""
        for cif in ["CIF-A", "CIF-B"]:
            for target in graph.results[cif].counterparties:
                spark_lt = graph.results[cif].counterparties[target].lifetime_summary
                pd_lt = pandas_graph.results[cif].counterparties[target].lifetime_summary
                assert spark_lt.total_inbound_amount == pytest.approx(pd_lt.total_inbound_amount, abs=0.01), (
                    f"{cif}→{target}: inbound {spark_lt.total_inbound_amount} vs {pd_lt.total_inbound_amount}"
                )
                assert spark_lt.total_outbound_amount == pytest.approx(pd_lt.total_outbound_amount, abs=0.01), (
                    f"{cif}→{target}: outbound {spark_lt.total_outbound_amount} vs {pd_lt.total_outbound_amount}"
                )

    def test_same_event_period(self, graph, pandas_graph):
        """Event period amounts match."""
        for cif in ["CIF-A", "CIF-B"]:
            for target in graph.results[cif].counterparties:
                spark_ev = graph.results[cif].counterparties[target].event_periods.get("event")
                pd_ev = pandas_graph.results[cif].counterparties[target].event_periods.get("event")
                if spark_ev and pd_ev:
                    assert spark_ev.inbound_amount == pytest.approx(pd_ev.inbound_amount, abs=0.01)
                    assert spark_ev.outbound_amount == pytest.approx(pd_ev.outbound_amount, abs=0.01)

    def test_same_relationship_profile(self, graph, pandas_graph):
        """Relationship flags match."""
        for cif in ["CIF-A", "CIF-B"]:
            for target in graph.results[cif].counterparties:
                spark_rel = graph.results[cif].counterparties[target].relationship
                pd_rel = pandas_graph.results[cif].counterparties[target].relationship
                assert spark_rel.is_bidirectional == pd_rel.is_bidirectional, (
                    f"{cif}→{target}: bidirectional {spark_rel.is_bidirectional} vs {pd_rel.is_bidirectional}"
                )
                assert spark_rel.is_new_in_event_period == pd_rel.is_new_in_event_period

    def test_self_transfer(self, pandas_graph):
        """Self-transfer detected in pandas engine."""
        cps = pandas_graph.results["CIF-A"].counterparties
        assert "CIF-A" in cps
        assert cps["CIF-A"].is_self_transfer is True

    def test_internal_external_profiles(self, pandas_graph):
        """Internal/external profiles assigned correctly."""
        cp_internal = pandas_graph.results["CIF-A"].counterparties["CIF-X"]
        assert cp_internal.target_is_internal is True
        assert cp_internal.internal_profile is not None

        cp_external = pandas_graph.results["CIF-A"].counterparties["ACC-EXT-1"]
        assert cp_external.target_is_internal is False
        assert cp_external.external_profile is not None

    def test_edge_count(self, pandas_graph):
        assert pandas_graph.edge_count > 0

    def test_node_count(self, pandas_graph):
        assert pandas_graph.node_count > 0

    def test_internal_ratio(self, pandas_graph):
        assert 0.0 <= pandas_graph.internal_ratio <= 1.0

    def test_get_node(self, pandas_graph):
        node = pandas_graph.get_node("CIF-A")
        assert node is not None
        assert len(node["counterparties"]) > 0

    def test_metrics(self, pandas_graph):
        assert pandas_graph.metrics.total_customers == 2
        assert pandas_graph.metrics.compute_time_seconds > 0

    def test_save_and_load(self, spark, pandas_graph, tmp_path):
        """Pandas graph can be saved and loaded back (as Spark)."""
        save_path = str(tmp_path / "saved_pd_graph")
        pandas_graph.save(save_path)

        loaded = load_counterparty_graph(spark, save_path)
        assert len(loaded.results) == len(pandas_graph.results)
        assert set(loaded.results.keys()) == set(pandas_graph.results.keys())

    def test_empty_contexts(self, spark, sample_transactions, sample_account_master, tmp_path):
        """Empty contexts → empty results with pandas engine too."""
        g = create_counterparty_graph(
            spark, sample_transactions, sample_account_master, [],
            engine="pandas",
        )
        assert g.results == {}

    def test_same_hub_detection(self, graph, pandas_graph):
        """Hub detection matches between engines."""
        for cif in ["CIF-A", "CIF-B"]:
            spark_s = graph.results[cif].summary
            pd_s = pandas_graph.results[cif].summary
            assert spark_s.hub_counterparties == pd_s.hub_counterparties, (
                f"{cif}: hubs {spark_s.hub_counterparties} vs {pd_s.hub_counterparties}"
            )

    def test_same_high_risk(self, graph, pandas_graph):
        """High risk count matches between engines."""
        for cif in ["CIF-A", "CIF-B"]:
            spark_s = graph.results[cif].summary
            pd_s = pandas_graph.results[cif].summary
            assert spark_s.high_risk_counterparties == pd_s.high_risk_counterparties, (
                f"{cif}: high_risk {spark_s.high_risk_counterparties} vs {pd_s.high_risk_counterparties}"
            )


class TestPandasCache:
    """Pandas engine caches intermediate pandas DataFrames as parquet."""

    def test_pandas_cache_files_exist(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc, tmp_path,
    ):
        """Pandas compute steps are cached as parquet files."""
        create_counterparty_graph(
            spark, sample_transactions, sample_account_master, sample_contexts,
            risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
            engine="pandas", cache_path=str(tmp_path), batch_id="pd_cache_test",
        )
        cache_dir = tmp_path / "pd_cache_test"
        cached_files = [f.name for f in cache_dir.iterdir()]
        for step in ["edge_table.parquet", "node_attrs.parquet",
                      "first_degree.parquet", "second_degree.parquet"]:
            assert step in cached_files, f"Missing cached step: {step}"

    def test_pandas_cache_reuse(
        self, spark, sample_transactions, sample_account_master, sample_contexts,
        sample_risk_scores, sample_labels, sample_kyc, tmp_path,
    ):
        """Second pandas run with same batch_id loads from cache and produces same results."""
        kwargs = dict(
            risk_scores=sample_risk_scores, labels=sample_labels, kyc=sample_kyc,
            engine="pandas", cache_path=str(tmp_path), batch_id="pd_reuse_test",
        )
        g1 = create_counterparty_graph(
            spark, sample_transactions, sample_account_master, sample_contexts,
            **kwargs,
        )
        g2 = create_counterparty_graph(
            spark, sample_transactions, sample_account_master, sample_contexts,
            **kwargs,
        )
        assert len(g1.results) == len(g2.results)
        assert set(g1.results.keys()) == set(g2.results.keys())
        for cif in g1.results:
            s1 = g1.results[cif].summary
            s2 = g2.results[cif].summary
            assert s1.total_counterparties == s2.total_counterparties
            assert s1.internal_count == s2.internal_count
            assert s1.external_count == s2.external_count
