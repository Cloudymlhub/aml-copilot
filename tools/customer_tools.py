"""Customer data retrieval tools - returns FACTUAL data only, no interpretation.

Uses service layer with dependency injection for database access.
"""

from typing import Optional, Dict, Any, List
from langchain.tools import BaseTool

from db.services import data_service


class GetCustomerBasicInfo(BaseTool):
    """Get basic customer information (identity, risk score, KYC status)."""

    name: str = "get_customer_basic_info"
    description: str = """Get basic customer information including:
    - CIF number, name, date of birth
    - Country, customer type, occupation
    - Risk score, KYC status, account opening date

    Input: Customer CIF number (e.g., 'C000001')
    Output: Dictionary with customer basic information
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get customer basic information."""
        customer = data_service.get_customer_basic(cif_no)

        if not customer:
            return {"error": f"Customer {cif_no} not found"}

        return customer.model_dump()


class GetCustomerTransactionFeatures(BaseTool):
    """Get customer transaction aggregation features (counts, amounts, averages)."""

    name: str = "get_customer_transaction_features"
    description: str = """Get customer transaction features including:
    - Transaction counts across time windows (0-30, 0-90, 0-180 days)
    - Transaction amount totals across time windows
    - Average transaction amounts
    - Maximum single transaction amounts
    - Cash transaction counts and amounts
    - International transaction metrics
    - High-risk country transaction counts

    Input: Customer CIF number (e.g., 'C000001')
    Output: Dictionary with transaction features
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get customer transaction features."""
        features = data_service.get_customer_transaction_features(cif_no)

        if not features:
            return {"error": f"Transaction features not found for customer {cif_no}"}

        return features.model_dump()


class GetCustomerRiskFeatures(BaseTool):
    """Get customer risk indicator features (PEP, sanctions, adverse media)."""

    name: str = "get_customer_risk_features"
    description: str = """Get customer risk indicator features including:
    - PEP (Politically Exposed Person) status
    - Sanctions list presence
    - Adverse media mentions count
    - High-risk country transactions count

    Input: Customer CIF number (e.g., 'C000001')
    Output: Dictionary with risk indicator features
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get customer risk features."""
        features = data_service.get_customer_risk_features(cif_no)

        if not features:
            return {"error": f"Risk features not found for customer {cif_no}"}

        return features.model_dump()


class GetCustomerBehavioralFeatures(BaseTool):
    """Get customer behavioral pattern features."""

    name: str = "get_customer_behavioral_features"
    description: str = """Get customer behavioral features including:
    - Account dormancy period (days since last transaction)
    - Transaction velocity change (recent vs historical)
    - Transaction amount deviation (recent vs historical average)

    Input: Customer CIF number (e.g., 'C000001')
    Output: Dictionary with behavioral features
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get customer behavioral features."""
        features = data_service.get_customer_behavioral_features(cif_no)

        if not features:
            return {"error": f"Behavioral features not found for customer {cif_no}"}

        return features.model_dump()


class GetCustomerNetworkFeatures(BaseTool):
    """Get customer network/graph features."""

    name: str = "get_customer_network_features"
    description: str = """Get customer network features including:
    - Network degree centrality (connectivity in transaction network)
    - Community ID (cluster/group in transaction network)
    - Unique counterparties count (0-90 days)
    - Average counterparty risk score

    Input: Customer CIF number (e.g., 'C000001')
    Output: Dictionary with network features
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get customer network features."""
        features = data_service.get_customer_network_features(cif_no)

        if not features:
            return {"error": f"Network features not found for customer {cif_no}"}

        return features.model_dump()


class GetCustomerKnowledgeGraphFeatures(BaseTool):
    """Get customer knowledge graph features (external entity relationships)."""

    name: str = "get_customer_knowledge_graph_features"
    description: str = """Get customer knowledge graph features including:
    - PEP exposure score (relationship proximity to PEPs)
    - Sanctions proximity score (relationship to sanctioned entities)
    - Adverse media sentiment score

    Input: Customer CIF number (e.g., 'C000001')
    Output: Dictionary with knowledge graph features
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get customer knowledge graph features."""
        features = data_service.get_customer_knowledge_graph_features(cif_no)

        if not features:
            return {"error": f"Knowledge graph features not found for customer {cif_no}"}

        return features.model_dump()


class GetCustomerFullProfile(BaseTool):
    """Get complete customer profile with all feature groups."""

    name: str = "get_customer_full_profile"
    description: str = """Get complete customer profile including:
    - Basic information
    - Transaction features
    - Risk features
    - Behavioral features
    - Network features
    - Knowledge graph features

    Input: Customer CIF number (e.g., 'C000001')
    Output: Dictionary with all feature groups
    """

    def _run(self, cif_no: str) -> Dict[str, Any]:
        """Get complete customer profile."""
        profile = data_service.get_customer_profile(
            cif_no,
            include_groups=[
                "transaction_features",
                "risk_features",
                "behavioral_features",
                "network_features",
                "knowledge_graph",
            ]
        )

        if not profile or not profile.get("basic"):
            return {"error": f"Customer {cif_no} not found"}

        # Serialize all groups using model_dump
        result = {"cif_no": cif_no}
        for group_name, group_data in profile.items():
            if group_data:
                result[group_name] = group_data.model_dump()

        return result


class SearchCustomersByName(BaseTool):
    """Search customers by name pattern."""

    name: str = "search_customers_by_name"
    description: str = """Search for customers by name pattern.

    Input: Name pattern to search (e.g., 'John', 'Smith')
    Output: List of matching customers with basic info
    """

    def _run(self, name_pattern: str, limit: int = 10) -> Dict[str, Any]:
        """Search customers by name."""
        customers = data_service.search_customers_by_name(name_pattern, limit=limit)

        if not customers:
            return {"results": [], "count": 0}

        return {
            "results": [c.model_dump() for c in customers],
            "count": len(customers),
        }


class CustomerDataTools:
    """Collection of customer data retrieval tools."""

    @staticmethod
    def get_tools() -> List[BaseTool]:
        """Get all customer data tools."""
        return [
            GetCustomerBasicInfo(),
            GetCustomerTransactionFeatures(),
            GetCustomerRiskFeatures(),
            GetCustomerBehavioralFeatures(),
            GetCustomerNetworkFeatures(),
            GetCustomerKnowledgeGraphFeatures(),
            GetCustomerFullProfile(),
            SearchCustomersByName(),
        ]
