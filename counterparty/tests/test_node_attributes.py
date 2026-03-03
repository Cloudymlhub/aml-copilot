"""Tests for node attribute computation."""

import pytest
from pyspark.sql import functions as F

from counterparty.counterparty_graph import _build_node_attributes


@pytest.fixture
def edge_cifs():
    """CIFs that appear in the edge table."""
    return {"CIF-A", "CIF-B", "CIF-X", "CIF-Y", "CIF-Z", "CIF-W"}


class TestComplianceAggregation:
    def test_cif_x_compliance(self, spark, sample_labels, sample_kyc, edge_cifs):
        """CIF-X: 1 alert (isL2=True has alert_generated_date), 1 case, 0 SARs."""
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-X").first()
        assert row is not None
        assert row["node_alert_count"] == 1
        assert row["node_case_count"] == 1
        assert row["node_sar_count"] == 0

    def test_cif_b_sar(self, spark, sample_labels, sample_kyc, edge_cifs):
        """CIF-B: has SAR."""
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-B").first()
        assert row["node_sar_count"] == 1

    def test_cif_y_clearance(self, spark, sample_labels, sample_kyc, edge_cifs):
        """CIF-Y: closed case = clearance."""
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-Y").first()
        assert row["node_clearance_count"] == 1
        assert row["node_last_clearance"] is not None


class TestOpenCaseDetection:
    def test_cif_x_open_case(self, spark, sample_labels, sample_kyc, edge_cifs):
        """CIF-X: case_date_close is NULL → has_open_case=True."""
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-X").first()
        assert row["node_has_open_case"] is True

    def test_cif_y_no_open_case(self, spark, sample_labels, sample_kyc, edge_cifs):
        """CIF-Y: case closed → has_open_case=False."""
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-Y").first()
        assert row["node_has_open_case"] is False


class TestKYCFields:
    def test_segment_populated(self, spark, sample_labels, sample_kyc, edge_cifs):
        """Known CIFs have segment populated."""
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-X").first()
        assert row["node_segment"] == "corporate"

    def test_declared_income(self, spark, sample_labels, sample_kyc, edge_cifs):
        """Known CIFs have declared_income populated."""
        nodes = _build_node_attributes(spark, sample_labels, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-A").first()
        assert row["node_declared_income"] == 200000.0


class TestNullInputs:
    def test_labels_none(self, spark, sample_kyc, edge_cifs):
        """labels=None → compliance columns default to 0/False/None."""
        nodes = _build_node_attributes(spark, None, sample_kyc, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-X").first()
        assert row["node_alert_count"] == 0
        assert row["node_has_open_case"] is False

    def test_kyc_none(self, spark, sample_labels, edge_cifs):
        """kyc=None → segment/income are null."""
        nodes = _build_node_attributes(spark, sample_labels, None, edge_cifs)
        row = nodes.filter(F.col("node_cif") == "CIF-X").first()
        assert row["node_segment"] is None
        assert row["node_declared_income"] is None

    def test_both_none(self, spark, edge_cifs):
        """Both None → all nodes present with defaults."""
        nodes = _build_node_attributes(spark, None, None, edge_cifs)
        assert nodes.count() == len(edge_cifs)

    def test_empty_cifs(self, spark, sample_labels, sample_kyc):
        """Empty edge_cifs → returns None."""
        result = _build_node_attributes(spark, sample_labels, sample_kyc, set())
        assert result is None
