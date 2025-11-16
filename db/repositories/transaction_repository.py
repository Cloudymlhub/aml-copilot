"""Transaction repository with raw SQL queries."""

from typing import List, Optional
from datetime import datetime
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor

from db.models.transaction import TransactionModel, TransactionCreate


class TransactionRepository:
    """Data access layer for transaction operations using raw SQL."""

    def get_by_id(
        self, conn: PGConnection, transaction_id: str
    ) -> Optional[TransactionModel]:
        """Get transaction by transaction ID."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM transactions
                WHERE transaction_id = %s
                """,
                (transaction_id,)
            )
            row = cur.fetchone()
            return TransactionModel(**row) if row else None

    def get_by_customer(
        self, conn: PGConnection, customer_id: int, limit: int = 100
    ) -> List[TransactionModel]:
        """Get all transactions for a customer."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM transactions
                WHERE customer_id = %s
                ORDER BY transaction_date DESC
                LIMIT %s
                """,
                (customer_id, limit)
            )
            rows = cur.fetchall()
            return [TransactionModel(**row) for row in rows]

    def get_by_customer_and_date_range(
        self,
        conn: PGConnection,
        customer_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> List[TransactionModel]:
        """Get transactions for a customer within date range."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM transactions
                WHERE customer_id = %s
                  AND transaction_date BETWEEN %s AND %s
                ORDER BY transaction_date DESC
                """,
                (customer_id, start_date, end_date)
            )
            rows = cur.fetchall()
            return [TransactionModel(**row) for row in rows]

    def get_by_amount_threshold(
        self,
        conn: PGConnection,
        customer_id: int,
        min_amount: float,
        limit: int = 100
    ) -> List[TransactionModel]:
        """Get transactions above amount threshold for a customer."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM transactions
                WHERE customer_id = %s
                  AND amount >= %s
                ORDER BY amount DESC, transaction_date DESC
                LIMIT %s
                """,
                (customer_id, min_amount, limit)
            )
            rows = cur.fetchall()
            return [TransactionModel(**row) for row in rows]

    def get_high_risk_transactions(
        self,
        conn: PGConnection,
        customer_id: Optional[int] = None,
        limit: int = 100
    ) -> List[TransactionModel]:
        """Get high-risk transactions (cash, structured, high-risk countries)."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT *
                FROM transactions
                WHERE (is_cash_transaction = TRUE
                   OR is_structured = TRUE
                   OR is_high_risk_country = TRUE
                   OR is_round_amount = TRUE)
            """
            params = []

            if customer_id is not None:
                query += " AND customer_id = %s"
                params.append(customer_id)

            query += " ORDER BY transaction_date DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [TransactionModel(**row) for row in rows]

    def get_international_transactions(
        self, conn: PGConnection, customer_id: int, limit: int = 100
    ) -> List[TransactionModel]:
        """Get international transactions for a customer."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM transactions
                WHERE customer_id = %s
                  AND is_international = TRUE
                ORDER BY transaction_date DESC
                LIMIT %s
                """,
                (customer_id, limit)
            )
            rows = cur.fetchall()
            return [TransactionModel(**row) for row in rows]

    def create(
        self, conn: PGConnection, transaction: TransactionCreate
    ) -> TransactionModel:
        """Create a new transaction."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO transactions (
                    transaction_id, customer_id, amount, currency,
                    transaction_date, transaction_type, channel,
                    counterparty_name, counterparty_country, description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    transaction.transaction_id,
                    transaction.customer_id,
                    transaction.amount,
                    transaction.currency,
                    transaction.transaction_date,
                    transaction.transaction_type,
                    transaction.channel,
                    transaction.counterparty_name,
                    transaction.counterparty_country,
                    transaction.description,
                ),
            )
            row = cur.fetchone()
            return TransactionModel(**row)

    def count_by_customer(self, conn: PGConnection, customer_id: int) -> int:
        """Count total transactions for a customer."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM transactions WHERE customer_id = %s",
                (customer_id,)
            )
            result = cur.fetchone()
            return result[0] if result else 0
