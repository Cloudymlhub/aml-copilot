"""Data service layer with caching and business logic."""

from typing import Optional, List, Any
from datetime import datetime

from db.manager import db_manager
from db.repositories.customer_repository import CustomerRepository
from db.repositories.transaction_repository import TransactionRepository
from db.repositories.alert_repository import AlertRepository
from db.services.cache_service import CacheService, cache_service
from db.models.customer import (
    CustomerBasic,
    CustomerTransactionFeatures,
    CustomerRiskFeatures,
    CustomerBehavioralFeatures,
    CustomerNetworkFeatures,
    CustomerKnowledgeGraphFeatures,
    CustomerFull,
)
from db.models.transaction import TransactionModel
from db.models.alert import AlertModel


class DataService:
    """Service layer for data access with caching and business logic."""

    def __init__(
        self,
        customer_repo: Optional[CustomerRepository] = None,
        transaction_repo: Optional[TransactionRepository] = None,
        alert_repo: Optional[AlertRepository] = None,
        cache: Optional[CacheService] = None,
    ):
        """Initialize data service.

        Args:
            customer_repo: Customer repository. If None, creates new instance.
            transaction_repo: Transaction repository. If None, creates new instance.
            alert_repo: Alert repository. If None, creates new instance.
            cache: Cache service. If None, uses global instance.
        """
        self.customer_repo = customer_repo or CustomerRepository()
        self.transaction_repo = transaction_repo or TransactionRepository()
        self.alert_repo = alert_repo or AlertRepository()
        self.cache = cache or cache_service

    # Customer methods with feature group caching

    def get_customer_basic(self, cif_no: str) -> Optional[CustomerBasic]:
        """Get customer basic info with caching.

        Cache key: customer:{cif_no}:basic
        TTL: 1 hour
        """
        # Check cache
        cached = self.cache.get_customer_feature_group(cif_no, "basic")
        if cached:
            return CustomerBasic(**cached)

        # Cache miss - fetch from DB
        with db_manager.get_connection() as conn:
            customer = self.customer_repo.get_basic(conn, cif_no)

        if customer:
            # Cache for future requests
            self.cache.set_customer_feature_group(
                cif_no, "basic", customer.model_dump()
            )

        return customer

    def get_customer_transaction_features(
        self, cif_no: str
    ) -> Optional[CustomerTransactionFeatures]:
        """Get customer transaction features with caching.

        Cache key: customer:{cif_no}:transaction_features
        TTL: 5 minutes
        """
        cached = self.cache.get_customer_feature_group(cif_no, "transaction_features")
        if cached:
            return CustomerTransactionFeatures(**cached)

        with db_manager.get_connection() as conn:
            features = self.customer_repo.get_transaction_features(conn, cif_no)

        if features:
            self.cache.set_customer_feature_group(
                cif_no, "transaction_features", features.model_dump()
            )

        return features

    def get_customer_risk_features(
        self, cif_no: str
    ) -> Optional[CustomerRiskFeatures]:
        """Get customer risk features with caching.

        Cache key: customer:{cif_no}:risk_features
        TTL: 5 minutes
        """
        cached = self.cache.get_customer_feature_group(cif_no, "risk_features")
        if cached:
            return CustomerRiskFeatures(**cached)

        with db_manager.get_connection() as conn:
            features = self.customer_repo.get_risk_features(conn, cif_no)

        if features:
            self.cache.set_customer_feature_group(
                cif_no, "risk_features", features.model_dump()
            )

        return features

    def get_customer_behavioral_features(
        self, cif_no: str
    ) -> Optional[CustomerBehavioralFeatures]:
        """Get customer behavioral features with caching.

        Cache key: customer:{cif_no}:behavioral_features
        TTL: 10 minutes
        """
        cached = self.cache.get_customer_feature_group(cif_no, "behavioral_features")
        if cached:
            return CustomerBehavioralFeatures(**cached)

        with db_manager.get_connection() as conn:
            features = self.customer_repo.get_behavioral_features(conn, cif_no)

        if features:
            self.cache.set_customer_feature_group(
                cif_no, "behavioral_features", features.model_dump()
            )

        return features

    def get_customer_network_features(
        self, cif_no: str
    ) -> Optional[CustomerNetworkFeatures]:
        """Get customer network features with caching.

        Cache key: customer:{cif_no}:network_features
        TTL: 30 minutes
        """
        cached = self.cache.get_customer_feature_group(cif_no, "network_features")
        if cached:
            return CustomerNetworkFeatures(**cached)

        with db_manager.get_connection() as conn:
            features = self.customer_repo.get_network_features(conn, cif_no)

        if features:
            self.cache.set_customer_feature_group(
                cif_no, "network_features", features.model_dump()
            )

        return features

    def get_customer_knowledge_graph_features(
        self, cif_no: str
    ) -> Optional[CustomerKnowledgeGraphFeatures]:
        """Get customer knowledge graph features with caching.

        Cache key: customer:{cif_no}:knowledge_graph
        TTL: 2 hours
        """
        cached = self.cache.get_customer_feature_group(cif_no, "knowledge_graph")
        if cached:
            return CustomerKnowledgeGraphFeatures(**cached)

        with db_manager.get_connection() as conn:
            features = self.customer_repo.get_knowledge_graph_features(conn, cif_no)

        if features:
            self.cache.set_customer_feature_group(
                cif_no, "knowledge_graph", features.model_dump()
            )

        return features

    def get_customer_profile(
        self, cif_no: str, include_groups: List[str]
    ) -> dict[str, Any]:
        """Get customer with specific feature groups.

        Args:
            cif_no: Customer CIF number
            include_groups: List of feature groups to include
                           (transaction_features, risk_features, behavioral_features,
                            network_features, knowledge_graph)

        Returns:
            Dict with 'basic' and requested feature groups.

        Example:
            profile = service.get_customer_profile(
                "C123",
                ["transaction_features", "risk_features"]
            )
            # Returns: {"basic": {...}, "transaction_features": {...}, "risk_features": {...}}
        """
        result = {}

        # Always fetch basic info
        result["basic"] = self.get_customer_basic(cif_no)

        # Fetch requested groups
        if "transaction_features" in include_groups:
            result["transaction_features"] = self.get_customer_transaction_features(cif_no)

        if "risk_features" in include_groups:
            result["risk_features"] = self.get_customer_risk_features(cif_no)

        if "behavioral_features" in include_groups:
            result["behavioral_features"] = self.get_customer_behavioral_features(cif_no)

        if "network_features" in include_groups:
            result["network_features"] = self.get_customer_network_features(cif_no)

        if "knowledge_graph" in include_groups:
            result["knowledge_graph"] = self.get_customer_knowledge_graph_features(cif_no)

        return result

    def get_high_risk_customers(
        self, threshold: float, limit: int = 100
    ) -> List[CustomerBasic]:
        """Get high-risk customers (not cached - changes frequently)."""
        with db_manager.get_connection() as conn:
            return self.customer_repo.get_high_risk_customers(conn, threshold, limit)

    def search_customers_by_name(
        self, name_pattern: str, limit: int = 10
    ) -> List[CustomerBasic]:
        """Search customers by name pattern."""
        with db_manager.get_connection() as conn:
            return self.customer_repo.search_by_name(conn, name_pattern, limit)

    # Transaction methods

    def get_transactions_by_cif(
        self, cif_no: str, limit: int = 100
    ) -> Optional[List[TransactionModel]]:
        """Get customer transactions by CIF with caching."""
        # Get customer first
        customer = self.get_customer_basic(cif_no)
        if not customer:
            return None

        cache_key = f"transactions:customer:{customer.id}:limit:{limit}"
        cached = self.cache.get_transaction_list(cache_key)
        if cached:
            return [TransactionModel(**t) for t in cached.get("transactions", [])]

        with db_manager.get_connection() as conn:
            transactions = self.transaction_repo.get_by_customer(conn, customer.id, limit)

        if transactions:
            serialized = [t.model_dump() for t in transactions]
            self.cache.set_transaction_list(cache_key, serialized, ttl=300)

        return transactions

    def get_high_risk_transactions_by_cif(
        self, cif_no: str, limit: int = 100
    ) -> Optional[List[TransactionModel]]:
        """Get high-risk transactions for customer by CIF."""
        customer = self.get_customer_basic(cif_no)
        if not customer:
            return None

        with db_manager.get_connection() as conn:
            return self.transaction_repo.get_high_risk_transactions(conn, customer.id, limit)

    def get_transactions_by_date_range(
        self, cif_no: str, start_date: str, end_date: str, limit: int = 50
    ) -> Optional[List[TransactionModel]]:
        """Get transactions in date range by CIF."""
        customer = self.get_customer_basic(cif_no)
        if not customer:
            return None

        with db_manager.get_connection() as conn:
            return self.transaction_repo.get_by_date_range(
                conn, customer.id, start_date, end_date, limit
            )

    def count_transactions_by_cif(self, cif_no: str) -> Optional[int]:
        """Count total transactions for customer by CIF."""
        customer = self.get_customer_basic(cif_no)
        if not customer:
            return None

        with db_manager.get_connection() as conn:
            return self.transaction_repo.count_by_customer(conn, customer.id)

    # Alert methods

    def get_alerts_by_cif(
        self, cif_no: str, limit: int = 50
    ) -> Optional[List[AlertModel]]:
        """Get customer alerts by CIF with caching."""
        customer = self.get_customer_basic(cif_no)
        if not customer:
            return None

        cache_key = f"alerts:customer:{customer.id}:limit:{limit}"
        cached = self.cache.get_alert_list(cache_key)
        if cached:
            return [AlertModel(**a) for a in cached]

        with db_manager.get_connection() as conn:
            alerts = self.alert_repo.get_by_customer(conn, customer.id, limit)

        if alerts:
            serialized = [a.model_dump() for a in alerts]
            self.cache.set_alert_list(cache_key, serialized, ttl=300)

        return alerts

    def get_open_alerts(self, limit: int = 100) -> List[AlertModel]:
        """Get open alerts (not cached - changes frequently)."""
        with db_manager.get_connection() as conn:
            return self.alert_repo.get_open_alerts(conn, limit)

    def get_alerts_by_severity(
        self, severity: str, limit: int = 100
    ) -> List[AlertModel]:
        """Get alerts by severity level."""
        with db_manager.get_connection() as conn:
            return self.alert_repo.get_by_severity(conn, severity, limit)

    def get_alerts_by_type(
        self, alert_type: str, limit: int = 100
    ) -> List[AlertModel]:
        """Get alerts by type."""
        with db_manager.get_connection() as conn:
            return self.alert_repo.get_by_type(conn, alert_type, limit)

    def get_alert_by_id(self, alert_id: str) -> Optional[AlertModel]:
        """Get alert by ID (not cached - infrequent query)."""
        with db_manager.get_connection() as conn:
            return self.alert_repo.get_by_id(conn, alert_id)

    # Cache invalidation helpers

    def invalidate_customer_cache(
        self, cif_no: str, groups: Optional[List[str]] = None
    ) -> int:
        """Invalidate customer cache groups.

        Args:
            cif_no: Customer CIF number
            groups: Specific groups to invalidate. If None, invalidates all.

        Returns:
            Number of cache keys deleted.
        """
        return self.cache.invalidate_customer(cif_no, groups)


# Global data service instance
data_service = DataService()
