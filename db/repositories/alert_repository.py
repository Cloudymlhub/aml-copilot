"""Alert repository with raw SQL queries."""

from typing import List, Optional
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor

from db.models.alert import AlertModel, AlertCreate, AlertUpdate


class AlertRepository:
    """Data access layer for alert operations using raw SQL."""

    def get_by_id(self, conn: PGConnection, alert_id: str) -> Optional[AlertModel]:
        """Get alert by alert ID."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                WHERE alert_id = %s
                """,
                (alert_id,)
            )
            row = cur.fetchone()
            return AlertModel(**row) if row else None

    def get_by_customer(
        self, conn: PGConnection, customer_id: int, limit: int = 50
    ) -> List[AlertModel]:
        """Get all alerts for a customer."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                WHERE customer_id = %s
                ORDER BY alert_date DESC
                LIMIT %s
                """,
                (customer_id, limit)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]

    def get_by_status(
        self, conn: PGConnection, status: str, limit: int = 100
    ) -> List[AlertModel]:
        """Get alerts by status (open, investigating, closed, escalated)."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                WHERE status = %s
                ORDER BY alert_date DESC
                LIMIT %s
                """,
                (status, limit)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]

    def get_by_severity(
        self, conn: PGConnection, severity: str, limit: int = 100
    ) -> List[AlertModel]:
        """Get alerts by severity (low, medium, high, critical)."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                WHERE severity = %s
                ORDER BY alert_date DESC
                LIMIT %s
                """,
                (severity, limit)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]

    def get_open_alerts(
        self, conn: PGConnection, limit: int = 100
    ) -> List[AlertModel]:
        """Get all open alerts (status = 'open' or 'investigating')."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                WHERE status IN ('open', 'investigating')
                ORDER BY severity DESC, alert_date DESC
                LIMIT %s
                """,
                (limit,)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]

    def get_by_type(
        self, conn: PGConnection, alert_type: str, limit: int = 100
    ) -> List[AlertModel]:
        """Get alerts by type (typology)."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                WHERE alert_type = %s
                ORDER BY alert_date DESC
                LIMIT %s
                """,
                (alert_type, limit)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]

    def get_assigned_to(
        self, conn: PGConnection, investigator: str, limit: int = 50
    ) -> List[AlertModel]:
        """Get alerts assigned to a specific investigator."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                WHERE assigned_to = %s
                  AND status IN ('open', 'investigating')
                ORDER BY severity DESC, alert_date DESC
                LIMIT %s
                """,
                (investigator, limit)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]

    def create(self, conn: PGConnection, alert: AlertCreate) -> AlertModel:
        """Create a new alert."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO alerts (
                    alert_id, customer_id, alert_type, alert_date,
                    severity, status, description, triggered_by_model,
                    model_confidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    alert.alert_id,
                    alert.customer_id,
                    alert.alert_type,
                    alert.alert_date,
                    alert.severity,
                    alert.status,
                    alert.description,
                    alert.triggered_by_model,
                    alert.model_confidence,
                ),
            )
            row = cur.fetchone()
            return AlertModel(**row)

    def update(
        self, conn: PGConnection, alert_id: str, update: AlertUpdate
    ) -> Optional[AlertModel]:
        """Update alert information."""
        # Build dynamic update query based on provided fields
        update_fields = []
        params = []

        if update.status is not None:
            update_fields.append("status = %s")
            params.append(update.status)

        if update.assigned_to is not None:
            update_fields.append("assigned_to = %s")
            params.append(update.assigned_to)

        if update.investigation_notes is not None:
            update_fields.append("investigation_notes = %s")
            params.append(update.investigation_notes)

        if update.severity is not None:
            update_fields.append("severity = %s")
            params.append(update.severity)

        if not update_fields:
            # Nothing to update
            return self.get_by_id(conn, alert_id)

        # Add updated_at
        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        # Add alert_id to params
        params.append(alert_id)

        query = f"""
            UPDATE alerts
            SET {', '.join(update_fields)}
            WHERE alert_id = %s
            RETURNING *
        """

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            return AlertModel(**row) if row else None

    def close_alert(self, conn: PGConnection, alert_id: str) -> bool:
        """Close an alert."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alerts
                SET status = 'closed',
                    closed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE alert_id = %s
                """,
                (alert_id,)
            )
            return cur.rowcount > 0

    def count_by_customer(self, conn: PGConnection, customer_id: int) -> int:
        """Count total alerts for a customer."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM alerts WHERE customer_id = %s",
                (customer_id,)
            )
            result = cur.fetchone()
            return result[0] if result else 0

    def get_open_alerts_by_cif(
        self, conn: PGConnection, cif_no: str, limit: int = 50
    ) -> List[AlertModel]:
        """Get open alerts for a customer by CIF number.

        Retrieves alerts with status 'open' or 'investigating' for the specified customer.
        This is useful for autonomous alert review workflows where analysts work with CIF numbers.

        Args:
            conn: Database connection
            cif_no: Customer CIF number (string identifier)
            limit: Maximum number of alerts to return (default: 50)

        Returns:
            List of AlertModel objects ordered by severity and date
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.*
                FROM alerts a
                JOIN customers c ON a.customer_id = c.id
                WHERE c.cif_no = %s
                  AND a.status IN ('open', 'investigating')
                ORDER BY
                  CASE a.severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                  END,
                  a.alert_date DESC
                LIMIT %s
                """,
                (cif_no, limit)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]

    def get_all_alerts_by_cif(
        self, conn: PGConnection, cif_no: str, limit: int = 100
    ) -> List[AlertModel]:
        """Get all alerts for a customer by CIF number (regardless of status).

        Retrieves complete alert history for the specified customer. Useful for
        understanding alert patterns and investigation history.

        Args:
            conn: Database connection
            cif_no: Customer CIF number (string identifier)
            limit: Maximum number of alerts to return (default: 100)

        Returns:
            List of AlertModel objects ordered by date (most recent first)
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.*
                FROM alerts a
                JOIN customers c ON a.customer_id = c.id
                WHERE c.cif_no = %s
                ORDER BY a.alert_date DESC
                LIMIT %s
                """,
                (cif_no, limit)
            )
            rows = cur.fetchall()
            return [AlertModel(**row) for row in rows]
