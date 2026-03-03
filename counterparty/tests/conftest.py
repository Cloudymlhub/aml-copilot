"""
Shared test fixtures for the Counterparty Graph module.

Test graph topology:
    CIF-Z ──→ ACC-1(CIF-X) ←── CIF-A ──→ ACC-EXT-1
                   ↑                ↓
                 CIF-B           ACC-A (self-loop, removed)
                   ↓
              ACC-Y(CIF-Y)
              ACC-EXT-2
         CIF-X ──→ ACC-3(CIF-W)
"""

from datetime import date

import pytest
from pyspark.sql import SparkSession

import sys
import os

# Add aml_copilot root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from counterparty.models import CaseContext, GraphParameters


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder.master("local[2]")
        .appName("counterparty-test")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "localhost")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.autoBroadcastJoinThreshold", "-1")
        .getOrCreate()
    )


@pytest.fixture
def sample_account_master(spark):
    """Authoritative account → CIF mapping."""
    return spark.createDataFrame(
        [
            ("ACC-1", "CIF-X"),
            ("ACC-Y", "CIF-Y"),
            ("ACC-A", "CIF-A"),  # CIF-A's own account (self-loop test)
            ("ACC-B", "CIF-B"),
            ("ACC-X1", "CIF-X"),  # CIF-X's second account (multi-account)
            ("ACC-3", "CIF-W"),  # 2nd degree outbound target
        ],
        ["foracid", "cif_no"],
    )


@pytest.fixture
def sample_transactions(spark):
    """Transactions covering all test scenarios."""
    return spark.createDataFrame(
        [
            # CIF-A transactions (review_date=2024-06-15)
            ("CIF-A", date(2024, 1, 10), "ACC-1", "Company X", "debit", 5000.0),
            ("CIF-A", date(2024, 3, 15), "ACC-1", "Company X", "debit", 8000.0),
            ("CIF-A", date(2024, 5, 20), "ACC-1", "Company X", "credit", 3000.0),
            ("CIF-A", date(2024, 6, 1), "ACC-1", "Company X", "debit", 15000.0),
            # multi-account (ACC-X1 → CIF-X)
            ("CIF-A", date(2024, 4, 10), "ACC-X1", "Company X", "debit", 2000.0),
            # external
            ("CIF-A", date(2024, 2, 5), "ACC-EXT-1", "Ext Corp", "debit", 12000.0),
            ("CIF-A", date(2024, 5, 10), "ACC-EXT-1", "Ext Corp", "credit", 4000.0),
            # self-loop (CIF-A → ACC-A = CIF-A)
            ("CIF-A", date(2024, 3, 1), "ACC-A", "Self Transfer", "debit", 1000.0),
            # outside lifetime window — should be filtered
            ("CIF-A", date(2023, 1, 1), "ACC-1", "Company X", "debit", 500.0),
            # CIF-B transactions (review_date=2024-07-01)
            ("CIF-B", date(2024, 4, 20), "ACC-1", "Company X", "debit", 7000.0),
            ("CIF-B", date(2024, 6, 15), "ACC-1", "Company X", "debit", 9000.0),
            ("CIF-B", date(2024, 5, 1), "ACC-Y", "Person Y", "debit", 3000.0),
            ("CIF-B", date(2024, 3, 10), "ACC-EXT-2", "Foreign Bank", "debit", 20000.0),
            # CIF-X own transactions (2nd degree outbound)
            ("CIF-X", date(2024, 4, 5), "ACC-3", "Supplier W", "debit", 6000.0),
            ("CIF-X", date(2024, 5, 15), "ACC-3", "Supplier W", "debit", 4500.0),
            ("CIF-X", date(2024, 6, 1), "ACC-EXT-1", "Ext Corp", "debit", 1000.0),
            # CIF-Z → ACC-1 (non-reviewed, inbound to CIF-X — 2nd degree)
            ("CIF-Z", date(2024, 5, 25), "ACC-1", "Company X", "credit", 11000.0),
        ],
        [
            "cif_no",
            "transaction_date",
            "counterparty_bank_account",
            "counterparty_name",
            "direction",
            "amount",
        ],
    )


@pytest.fixture
def sample_risk_scores(spark):
    """Daily risk scores with multiple dates per CIF."""
    return spark.createDataFrame(
        [
            ("CIF-X", date(2024, 3, 1), 0.75),
            ("CIF-X", date(2024, 4, 1), 0.80),
            ("CIF-X", date(2024, 5, 1), 0.85),
            ("CIF-X", date(2024, 6, 1), 0.82),
            ("CIF-X", date(2023, 6, 1), 0.90),  # outside rating window
            ("CIF-B", date(2024, 4, 1), 0.15),
            ("CIF-B", date(2024, 5, 1), 0.20),
            ("CIF-B", date(2024, 6, 1), 0.18),
            ("CIF-Y", date(2024, 5, 1), 0.50),
            ("CIF-Y", date(2024, 6, 1), 0.55),
            ("CIF-A", date(2024, 5, 1), 0.30),
            ("CIF-A", date(2024, 6, 1), 0.35),
        ],
        ["cif_no", "observation_date", "score"],
    )


@pytest.fixture
def sample_labels(spark):
    """Compliance lifecycle events."""
    return spark.createDataFrame(
        [
            ("CIF-X", True, False, date(2024, 3, 1), date(2024, 4, 1), None),
            ("CIF-B", False, True, date(2024, 2, 1), None, None),
            ("CIF-Y", True, False, date(2024, 1, 15), date(2024, 2, 1), date(2024, 3, 1)),
            ("CIF-A", True, False, date(2024, 5, 1), None, None),
        ],
        [
            "cif_no",
            "isL2",
            "isSAR",
            "alert_generated_date",
            "case_date_open",
            "case_date_close",
        ],
    )


@pytest.fixture
def sample_kyc(spark):
    """Static customer profiles."""
    return spark.createDataFrame(
        [
            ("CIF-X", "corporate", 1000000.0),
            ("CIF-Y", "retail", 50000.0),
            ("CIF-B", "retail", 75000.0),
            ("CIF-A", "sme", 200000.0),
        ],
        ["cif_no", "segment", "declared_income"],
    )


@pytest.fixture
def sample_contexts():
    """Two CaseContexts with DIFFERENT review dates."""
    return [
        CaseContext(cif_no="CIF-A", review_date=date(2024, 6, 15)),
        CaseContext(cif_no="CIF-B", review_date=date(2024, 7, 1)),
    ]


@pytest.fixture
def default_params():
    """Default graph parameters."""
    return GraphParameters()
