"""Transaction data retrieval tools - returns FACTUAL data only, no interpretation.

Uses service layer with dependency injection for database access.
"""

from typing import Dict, Any, List
from langchain.tools import BaseTool

from db.services import data_service


class GetCustomerTransactions(BaseTool):
    """Get transactions for a specific customer."""

    name: str = "get_customer_transactions"
    description: str = """Get transactions for a specific customer including:
    - Transaction ID, date, amount, currency
    - Transaction type (credit/debit)
    - Channel (online, branch, ATM, etc.)
    - Counterparty information
    - Flags (cash transaction, structured, high-risk country)

    Input: Customer CIF number (e.g., 'C000001') and optional limit (default 10)
    Output: List of transactions with details
    """

    def _run(self, cif_no: str, limit: int = 10) -> Dict[str, Any]:
        """Get customer transactions."""
        transactions = data_service.get_transactions_by_cif(cif_no, limit=limit)

        if transactions is None:
            return {"error": f"Customer {cif_no} not found"}

        if not transactions:
            return {"cif_no": cif_no, "transactions": [], "count": 0}

        return {
            "cif_no": cif_no,
            "transactions": [t.model_dump(mode='json') for t in transactions],
            "count": len(transactions),
        }


class GetHighRiskTransactions(BaseTool):
    """Get high-risk transactions for a specific customer."""

    name: str = "get_high_risk_transactions"
    description: str = """Get transactions flagged as high-risk for a customer.
    High-risk transactions may have one or more flags:
    - Cash transaction
    - Structured transaction (potentially structuring to avoid reporting)
    - High-risk country counterparty

    Input: Customer CIF number (e.g., 'C000001') and optional limit (default 10)
    Output: List of high-risk transactions with flag details
    """

    def _run(self, cif_no: str, limit: int = 10) -> Dict[str, Any]:
        """Get high-risk transactions."""
        transactions = data_service.get_high_risk_transactions_by_cif(cif_no, limit=limit)

        if transactions is None:
            return {"error": f"Customer {cif_no} not found"}

        if not transactions:
            return {"cif_no": cif_no, "transactions": [], "count": 0}

        return {
            "cif_no": cif_no,
            "transactions": [t.model_dump(mode='json') for t in transactions],
            "count": len(transactions),
        }


class GetTransactionCount(BaseTool):
    """Get total transaction count for a customer."""

    name: str = "get_transaction_count"
    description: str = """Get total number of transactions for a customer.

    Input: Customer CIF number (e.g., 'C000001')
    Output: Total transaction count
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get transaction count."""
        count = data_service.count_transactions_by_cif(cif_no)

        if count is None:
            return {"error": f"Customer {cif_no} not found"}

        return {
            "cif_no": cif_no,
            "transaction_count": count,
        }


class GetTransactionsByDateRange(BaseTool):
    """Get transactions within a specific date range."""

    name: str = "get_transactions_by_date_range"
    description: str = """Get transactions for a customer within a date range.

    Input: Customer CIF number, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), optional limit (default 50)
    Output: List of transactions within date range
    """

    def _run(
        self,
        cif_no: str,
        start_date: str,
        end_date: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get transactions by date range."""
        transactions = data_service.get_transactions_by_date_range(
            cif_no, start_date, end_date, limit=limit
        )

        if transactions is None:
            return {"error": f"Customer {cif_no} not found"}

        if not transactions:
            return {
                "cif_no": cif_no,
                "start_date": start_date,
                "end_date": end_date,
                "transactions": [],
                "count": 0,
            }

        return {
            "cif_no": cif_no,
            "start_date": start_date,
            "end_date": end_date,
            "transactions": [t.model_dump(mode='json') for t in transactions],
            "count": len(transactions),
        }


class TransactionDataTools:
    """Collection of transaction data retrieval tools."""

    @staticmethod
    def get_tools() -> List[BaseTool]:
        """Get all transaction data tools."""
        return [
            GetCustomerTransactions(),
            GetHighRiskTransactions(),
            GetTransactionCount(),
            GetTransactionsByDateRange(),
        ]
