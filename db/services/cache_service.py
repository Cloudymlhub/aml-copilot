"""Redis cache service for feature group caching."""

import json
from typing import Any, Optional
import redis
from redis import Redis

from config.settings import settings


class CacheService:
    """Redis caching service with feature group support."""

    # TTL strategy based on feature group update frequency
    CACHE_TTL = {
        "basic": 3600,                    # 1 hour (identity changes rarely)
        "transaction_features": 300,      # 5 minutes (updated frequently)
        "risk_features": 300,             # 5 minutes (recalculated often)
        "behavioral_features": 600,       # 10 minutes (medium frequency)
        "network_features": 1800,         # 30 minutes (graph analysis is expensive)
        "knowledge_graph": 7200,          # 2 hours (external data, slow to change)
        "default": 600,                   # 10 minutes (fallback)
    }

    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize cache service.

        Args:
            redis_client: Optional Redis client. If None, creates new connection.
        """
        if redis_client is None:
            self.redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,  # Automatically decode responses to strings
            )
        else:
            self.redis = redis_client

    def _make_key(self, entity_type: str, entity_id: str, group_name: Optional[str] = None) -> str:
        """Create cache key.

        Pattern: {entity_type}:{entity_id}:{group_name}
        Example: customer:C123:transaction_features
        """
        if group_name:
            return f"{entity_type}:{entity_id}:{group_name}"
        return f"{entity_type}:{entity_id}"

    def get(self, key: str) -> Optional[dict]:
        """Get value from cache.

        Returns:
            Dict if found, None if not found or error.
        """
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            # Log error but don't fail - cache miss is safe
            print(f"Cache get error for key {key}: {e}")
            return None

    def set(self, key: str, value: dict, ttl: Optional[int] = None) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Dict to cache (will be JSON serialized)
            ttl: Time to live in seconds. If None, uses default.

        Returns:
            True if successful, False otherwise.
        """
        try:
            serialized = json.dumps(value, default=str)  # default=str handles datetime, Decimal
            if ttl is None:
                ttl = self.CACHE_TTL["default"]
            self.redis.setex(key, ttl, serialized)
            return True
        except (redis.RedisError, TypeError, ValueError) as e:
            # Log error but don't fail - cache write failure is safe
            print(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache.

        Returns:
            True if key was deleted, False otherwise.
        """
        try:
            return self.redis.delete(key) > 0
        except redis.RedisError as e:
            print(f"Cache delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., "customer:C123:*")

        Returns:
            Number of keys deleted.
        """
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except redis.RedisError as e:
            print(f"Cache delete pattern error for {pattern}: {e}")
            return 0

    def get_customer_feature_group(
        self, cif_no: str, group_name: str
    ) -> Optional[dict]:
        """Get customer feature group from cache.

        Args:
            cif_no: Customer CIF number
            group_name: Feature group name (basic, transaction_features, etc.)

        Returns:
            Feature group dict if found, None otherwise.
        """
        key = self._make_key("customer", cif_no, group_name)
        return self.get(key)

    def set_customer_feature_group(
        self, cif_no: str, group_name: str, data: dict
    ) -> bool:
        """Set customer feature group in cache.

        Args:
            cif_no: Customer CIF number
            group_name: Feature group name
            data: Feature group data to cache

        Returns:
            True if successful, False otherwise.
        """
        key = self._make_key("customer", cif_no, group_name)
        ttl = self.CACHE_TTL.get(group_name, self.CACHE_TTL["default"])
        return self.set(key, data, ttl)

    def invalidate_customer(self, cif_no: str, group_names: Optional[list[str]] = None) -> int:
        """Invalidate customer cache.

        Args:
            cif_no: Customer CIF number
            group_names: Specific groups to invalidate. If None, invalidates all groups.

        Returns:
            Number of keys deleted.
        """
        if group_names:
            # Invalidate specific groups
            count = 0
            for group_name in group_names:
                key = self._make_key("customer", cif_no, group_name)
                if self.delete(key):
                    count += 1
            return count
        else:
            # Invalidate all customer groups
            pattern = self._make_key("customer", cif_no, "*")
            return self.delete_pattern(pattern)

    def get_transaction_list(self, cache_key: str) -> Optional[list]:
        """Get cached transaction list."""
        cached = self.get(cache_key)
        return cached if cached else None

    def set_transaction_list(self, cache_key: str, transactions: list, ttl: int = 300) -> bool:
        """Cache transaction list."""
        return self.set(cache_key, {"transactions": transactions}, ttl)

    def get_alert_list(self, cache_key: str) -> Optional[list]:
        """Get cached alert list."""
        cached = self.get(cache_key)
        return cached.get("alerts") if cached else None

    def set_alert_list(self, cache_key: str, alerts: list, ttl: int = 300) -> bool:
        """Cache alert list."""
        return self.set(cache_key, {"alerts": alerts}, ttl)

    def health_check(self) -> bool:
        """Check if Redis is accessible.

        Returns:
            True if Redis is healthy, False otherwise.
        """
        try:
            return self.redis.ping()
        except redis.RedisError:
            return False

    def flush_all(self) -> bool:
        """Flush all cache (use with caution!).

        Returns:
            True if successful, False otherwise.
        """
        try:
            self.redis.flushdb()
            return True
        except redis.RedisError as e:
            print(f"Cache flush error: {e}")
            return False


# Global cache service instance
cache_service = CacheService()
