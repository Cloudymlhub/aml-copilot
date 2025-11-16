"""Customer repository with raw SQL queries and feature group support."""

from typing import Optional, List
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor

from db.models.customer import (
    CustomerBasic,
    CustomerTransactionFeatures,
    CustomerRiskFeatures,
    CustomerBehavioralFeatures,
    CustomerNetworkFeatures,
    CustomerKnowledgeGraphFeatures,
    CustomerFull,
    CustomerCreate,
)


class CustomerRepository:
    """Data access layer for customer operations using raw SQL."""

    def get_basic(self, conn: PGConnection, cif_no: str) -> Optional[CustomerBasic]:
        """Get basic customer info (identity + risk score).

        Use this for: Quick lookups, risk checks, profile display.
        Query cost: 9 columns.
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, cif_no, name, date_of_birth, country, kyc_status,
                       account_opened_date, occupation, industry, risk_score,
                       created_at, updated_at
                FROM customers
                WHERE cif_no = %s
                """,
                (cif_no,)
            )
            row = cur.fetchone()
            return CustomerBasic(**row) if row else None

    def get_basic_by_id(self, conn: PGConnection, customer_id: int) -> Optional[CustomerBasic]:
        """Get basic customer info by database ID."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, cif_no, name, date_of_birth, country, kyc_status,
                       account_opened_date, occupation, industry, risk_score,
                       created_at, updated_at
                FROM customers
                WHERE id = %s
                """,
                (customer_id,)
            )
            row = cur.fetchone()
            return CustomerBasic(**row) if row else None

    def get_transaction_features(
        self, conn: PGConnection, cif_no: str
    ) -> Optional[CustomerTransactionFeatures]:
        """Get transaction aggregation features.

        Returns ALL transaction features from DB (dynamic, not hardcoded).
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT cif_no,
                       sum_txn_count_w0_30, sum_txn_amount_w0_30,
                       avg_txn_amount_w0_30, max_txn_amount_w0_30,
                       min_txn_amount_w0_30, std_txn_amount_w0_30,
                       sum_txn_count_w0_90, sum_txn_amount_w0_90,
                       avg_txn_amount_w0_90, max_txn_amount_w0_90,
                       sum_txn_count_w30_60, avg_txn_amount_w30_60,
                       sum_txn_count_w0_180, sum_txn_amount_w0_180,
                       max_single_txn_w0_180
                FROM customers
                WHERE cif_no = %s
                """,
                (cif_no,)
            )
            row = cur.fetchone()
            return CustomerTransactionFeatures(**row) if row else None

    def get_risk_features(
        self, conn: PGConnection, cif_no: str
    ) -> Optional[CustomerRiskFeatures]:
        """Get risk indicator features."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT cif_no,
                       count_high_risk_countries_w0_90,
                       count_cash_intensive_txn_w0_90,
                       count_round_amount_txn_w0_90,
                       ratio_international_txn_w0_90
                FROM customers
                WHERE cif_no = %s
                """,
                (cif_no,)
            )
            row = cur.fetchone()
            return CustomerRiskFeatures(**row) if row else None

    def get_behavioral_features(
        self, conn: PGConnection, cif_no: str
    ) -> Optional[CustomerBehavioralFeatures]:
        """Get behavioral pattern features."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT cif_no,
                       count_atm_withdrawals_w0_30,
                       count_wire_transfers_w0_90,
                       velocity_score_w0_30
                FROM customers
                WHERE cif_no = %s
                """,
                (cif_no,)
            )
            row = cur.fetchone()
            return CustomerBehavioralFeatures(**row) if row else None

    def get_network_features(
        self, conn: PGConnection, cif_no: str
    ) -> Optional[CustomerNetworkFeatures]:
        """Get network/graph analysis features."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT cif_no,
                       network_degree_centrality,
                       network_community_id,
                       count_unique_counterparties_w0_90,
                       count_shared_counterparties
                FROM customers
                WHERE cif_no = %s
                """,
                (cif_no,)
            )
            row = cur.fetchone()
            return CustomerNetworkFeatures(**row) if row else None

    def get_knowledge_graph_features(
        self, conn: PGConnection, cif_no: str
    ) -> Optional[CustomerKnowledgeGraphFeatures]:
        """Get knowledge graph features (PEP, sanctions, adverse media)."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT cif_no,
                       pep_exposure_score,
                       adverse_media_score,
                       sanction_list_proximity
                FROM customers
                WHERE cif_no = %s
                """,
                (cif_no,)
            )
            row = cur.fetchone()
            return CustomerKnowledgeGraphFeatures(**row) if row else None

    def get_full(self, conn: PGConnection, cif_no: str) -> Optional[CustomerFull]:
        """Get complete customer profile with all features.

        Use sparingly - fetches 40+ columns.
        Prefer fetching specific feature groups based on use case.
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM customers
                WHERE cif_no = %s
                """,
                (cif_no,)
            )
            row = cur.fetchone()
            return CustomerFull(**row) if row else None

    def get_high_risk_customers(
        self, conn: PGConnection, threshold: float, limit: int = 100
    ) -> List[CustomerBasic]:
        """Get customers above risk threshold."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, cif_no, name, date_of_birth, country, kyc_status,
                       account_opened_date, occupation, industry, risk_score,
                       created_at, updated_at
                FROM customers
                WHERE risk_score > %s
                ORDER BY risk_score DESC
                LIMIT %s
                """,
                (threshold, limit)
            )
            rows = cur.fetchall()
            return [CustomerBasic(**row) for row in rows]

    def search_by_name(
        self, conn: PGConnection, name_pattern: str, limit: int = 50
    ) -> List[CustomerBasic]:
        """Search customers by name (case-insensitive)."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, cif_no, name, date_of_birth, country, kyc_status,
                       account_opened_date, occupation, industry, risk_score,
                       created_at, updated_at
                FROM customers
                WHERE name ILIKE %s
                ORDER BY name
                LIMIT %s
                """,
                (f"%{name_pattern}%", limit)
            )
            rows = cur.fetchall()
            return [CustomerBasic(**row) for row in rows]

    def create(self, conn: PGConnection, customer: CustomerCreate) -> CustomerBasic:
        """Create a new customer.

        Note: ML features are computed later by feature engineering pipeline.
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO customers (
                    cif_no, name, date_of_birth, country, kyc_status,
                    account_opened_date, occupation, industry
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, cif_no, name, date_of_birth, country, kyc_status,
                          account_opened_date, occupation, industry, risk_score,
                          created_at, updated_at
                """,
                (
                    customer.cif_no,
                    customer.name,
                    customer.date_of_birth,
                    customer.country,
                    customer.kyc_status,
                    customer.account_opened_date,
                    customer.occupation,
                    customer.industry,
                ),
            )
            row = cur.fetchone()
            return CustomerBasic(**row)

    def update_risk_score(
        self, conn: PGConnection, cif_no: str, risk_score: float
    ) -> bool:
        """Update customer risk score."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                SET risk_score = %s, updated_at = CURRENT_TIMESTAMP
                WHERE cif_no = %s
                """,
                (risk_score, cif_no)
            )
            return cur.rowcount > 0

    def exists(self, conn: PGConnection, cif_no: str) -> bool:
        """Check if customer exists."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM customers WHERE cif_no = %s",
                (cif_no,)
            )
            return cur.fetchone() is not None
