"""Alert data retrieval tools - returns FACTUAL data only, no interpretation.

Uses service layer with dependency injection for database access.
"""

from typing import Dict, Any, List
from langchain.tools import BaseTool

from db.services import data_service


class GetOpenAlerts(BaseTool):
    """Get all open alerts in the system."""

    name: str = "get_open_alerts"
    description: str = """Get all open (unresolved) alerts including:
    - Alert ID, type, severity
    - Associated customer CIF
    - Alert description
    - Created date

    Input: Optional limit (default 20)
    Output: List of open alerts
    """

    def _run(self, limit: int = 20) -> Dict[str, Any]:
        """Get open alerts."""
        alerts = data_service.get_open_alerts(limit=limit)

        if not alerts:
            return {"alerts": [], "count": 0}

        return {
            "alerts": [a.model_dump(mode='json') for a in alerts],
            "count": len(alerts),
        }


class GetAlertsBySeverity(BaseTool):
    """Get alerts by severity level."""

    name: str = "get_alerts_by_severity"
    description: str = """Get alerts filtered by severity level.

    Severity levels: low, medium, high, critical

    Input: Severity level (e.g., 'high', 'critical') and optional limit (default 20)
    Output: List of alerts with specified severity
    """

    def _run(self, severity: str, limit: int = 20) -> Dict[str, Any]:
        """Get alerts by severity."""
        alerts = data_service.get_alerts_by_severity(severity, limit=limit)

        if not alerts:
            return {"severity": severity, "alerts": [], "count": 0}

        return {
            "severity": severity,
            "alerts": [a.model_dump(mode='json') for a in alerts],
            "count": len(alerts),
        }


class GetAlertsByType(BaseTool):
    """Get alerts by alert type."""

    name: str = "get_alerts_by_type"
    description: str = """Get alerts filtered by alert type.

    Common alert types: structuring, large_cash_transaction, unusual_pattern,
                        high_risk_country, pep_transaction, etc.

    Input: Alert type (e.g., 'structuring') and optional limit (default 20)
    Output: List of alerts of specified type
    """

    def _run(self, alert_type: str, limit: int = 20) -> Dict[str, Any]:
        """Get alerts by type."""
        alerts = data_service.get_alerts_by_type(alert_type, limit=limit)

        if not alerts:
            return {"alert_type": alert_type, "alerts": [], "count": 0}

        return {
            "alert_type": alert_type,
            "alerts": [a.model_dump(mode='json') for a in alerts],
            "count": len(alerts),
        }


class GetCustomerAlerts(BaseTool):
    """Get all alerts for a specific customer."""

    name: str = "get_customer_alerts"
    description: str = """Get all alerts associated with a specific customer.

    Input: Customer CIF number (e.g., 'C000001') and optional limit (default 20)
    Output: List of alerts for the customer
    """

    def _run(self, cif_no: str, limit: int = 20) -> Dict[str, Any]:
        """Get customer alerts."""
        alerts = data_service.get_alerts_by_cif(cif_no, limit=limit)

        if alerts is None:
            return {"error": f"Customer {cif_no} not found"}

        if not alerts:
            return {"cif_no": cif_no, "alerts": [], "count": 0}

        return {
            "cif_no": cif_no,
            "alerts": [a.model_dump(mode='json') for a in alerts],
            "count": len(alerts),
        }


class GetAlertDetails(BaseTool):
    """Get detailed information for a specific alert."""

    name: str = "get_alert_details"
    description: str = """Get complete details for a specific alert.

    Input: Alert ID (e.g., 'A000001')
    Output: Complete alert details including resolution information
    """

    def _run(self, alert_id: str) -> Dict[str, Any]:
        """Get alert details."""
        alert = data_service.get_alert_by_id(alert_id)

        if not alert:
            return {"error": f"Alert {alert_id} not found"}

        return alert.model_dump(mode='json')


class AlertDataTools:
    """Collection of alert data retrieval tools."""

    @staticmethod
    def get_tools() -> List[BaseTool]:
        """Get all alert data tools."""
        return [
            GetOpenAlerts(),
            GetAlertsBySeverity(),
            GetAlertsByType(),
            GetCustomerAlerts(),
            GetAlertDetails(),
        ]
