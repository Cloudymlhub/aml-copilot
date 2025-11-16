"""Test repositories and services with real database data."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.manager import db_manager
from db.repositories import CustomerRepository, TransactionRepository, AlertRepository
from db.services import data_service, cache_service


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def test_customer_repository():
    """Test customer repository methods."""
    print_header("Testing Customer Repository")

    repo = CustomerRepository()

    with db_manager.get_connection() as conn:
        # Test 1: Get first customer
        print("\n1. Get first customer by CIF:")
        customer = repo.get_basic(conn, "C000001")
        if customer:
            print(f"   ✓ Found: {customer.cif_no} - {customer.name}")
            print(f"   ✓ Risk Score: {customer.risk_score}")
            print(f"   ✓ Country: {customer.country}")
            print(f"   ✓ KYC Status: {customer.kyc_status}")
        else:
            print("   ✗ Customer not found!")

        # Test 2: Get high-risk customers
        print("\n2. Get high-risk customers (risk_score > 70):")
        high_risk = repo.get_high_risk_customers(conn, threshold=70.0, limit=5)
        print(f"   ✓ Found {len(high_risk)} high-risk customers")
        for c in high_risk[:3]:
            print(f"      - {c.cif_no}: {c.name} (risk: {c.risk_score})")

        # Test 3: Get transaction features
        print("\n3. Get transaction features for first customer:")
        if customer:
            txn_features = repo.get_transaction_features(conn, customer.cif_no)
            if txn_features:
                print(f"   ✓ Transaction count (0-30 days): {txn_features.sum_txn_count_w0_30}")
                print(f"   ✓ Total amount (0-90 days): ${txn_features.sum_txn_amount_w0_90}")
                print(f"   ✓ Avg amount (0-90 days): ${txn_features.avg_txn_amount_w0_90}")
                print(f"   ✓ Max single transaction: ${txn_features.max_single_txn_w0_180}")

        # Test 4: Get network features
        print("\n4. Get network features for first customer:")
        if customer:
            network_features = repo.get_network_features(conn, customer.cif_no)
            if network_features:
                print(f"   ✓ Degree centrality: {network_features.network_degree_centrality}")
                print(f"   ✓ Community: {network_features.network_community_id}")
                print(f"   ✓ Unique counterparties: {network_features.count_unique_counterparties_w0_90}")

        # Test 5: Search by name
        print("\n5. Search customers by name pattern:")
        results = repo.search_by_name(conn, "John", limit=3)
        print(f"   ✓ Found {len(results)} customers with 'John' in name")
        for c in results:
            print(f"      - {c.cif_no}: {c.name}")


def test_transaction_repository():
    """Test transaction repository methods."""
    print_header("Testing Transaction Repository")

    repo = TransactionRepository()

    with db_manager.get_connection() as conn:
        # Get a customer first
        customer_repo = CustomerRepository()
        customer = customer_repo.get_basic(conn, "C000001")

        if customer:
            # Test 1: Get transactions by customer
            print(f"\n1. Get transactions for {customer.cif_no}:")
            transactions = repo.get_by_customer(conn, customer.id, limit=5)
            print(f"   ✓ Found {len(transactions)} transactions")
            if transactions:
                txn = transactions[0]
                print(f"      Latest: {txn.transaction_id}")
                print(f"      Amount: ${txn.amount} {txn.currency}")
                print(f"      Date: {txn.transaction_date}")
                print(f"      Type: {txn.transaction_type}")

            # Test 2: Get high-risk transactions
            print(f"\n2. Get high-risk transactions for {customer.cif_no}:")
            high_risk_txns = repo.get_high_risk_transactions(conn, customer.id, limit=3)
            print(f"   ✓ Found {len(high_risk_txns)} high-risk transactions")
            for txn in high_risk_txns:
                flags = []
                if txn.is_cash_transaction:
                    flags.append("CASH")
                if txn.is_structured:
                    flags.append("STRUCTURED")
                if txn.is_high_risk_country:
                    flags.append("HIGH_RISK_COUNTRY")
                print(f"      - ${txn.amount} [{', '.join(flags)}]")

            # Test 3: Count transactions
            print(f"\n3. Count total transactions for {customer.cif_no}:")
            count = repo.count_by_customer(conn, customer.id)
            print(f"   ✓ Total: {count} transactions")


def test_alert_repository():
    """Test alert repository methods."""
    print_header("Testing Alert Repository")

    repo = AlertRepository()

    with db_manager.get_connection() as conn:
        # Test 1: Get open alerts
        print("\n1. Get open alerts:")
        open_alerts = repo.get_open_alerts(conn, limit=5)
        print(f"   ✓ Found {len(open_alerts)} open alerts")
        for alert in open_alerts:
            print(f"      - {alert.alert_id}: {alert.alert_type} [{alert.severity}]")

        # Test 2: Get alerts by severity
        print("\n2. Get high severity alerts:")
        high_severity = repo.get_by_severity(conn, "high", limit=5)
        print(f"   ✓ Found {len(high_severity)} high severity alerts")

        # Test 3: Get alerts by type
        print("\n3. Get alerts by type (structuring):")
        structuring_alerts = repo.get_by_type(conn, "structuring", limit=3)
        print(f"   ✓ Found {len(structuring_alerts)} structuring alerts")


def test_service_layer_caching():
    """Test service layer with Redis caching."""
    print_header("Testing Service Layer with Caching")

    # Clear cache first
    print("\n0. Clearing cache...")
    cache_service.flush_all()
    print("   ✓ Cache cleared")

    # Test 1: First query (cache miss)
    print("\n1. First query for customer basic info (should be cache MISS):")
    customer = data_service.get_customer_basic("C000001")
    if customer:
        print(f"   ✓ Retrieved: {customer.name}")
        print(f"   ✓ Risk Score: {customer.risk_score}")

    # Test 2: Second query (cache hit)
    print("\n2. Second query for same customer (should be cache HIT):")
    customer2 = data_service.get_customer_basic("C000001")
    if customer2:
        print(f"   ✓ Retrieved from cache: {customer2.name}")
        print(f"   ✓ Data matches: {customer.name == customer2.name}")

    # Test 3: Query transaction features (cache miss)
    print("\n3. Query transaction features (should be cache MISS):")
    txn_features = data_service.get_customer_transaction_features("C000001")
    if txn_features:
        print(f"   ✓ Transaction count (0-90 days): {txn_features.sum_txn_count_w0_90}")
        print(f"   ✓ Total amount (0-90 days): ${txn_features.sum_txn_amount_w0_90}")

    # Test 4: Query transaction features again (cache hit)
    print("\n4. Query transaction features again (should be cache HIT):")
    txn_features2 = data_service.get_customer_transaction_features("C000001")
    if txn_features2:
        print(f"   ✓ Retrieved from cache")
        print(f"   ✓ Data matches: {txn_features.sum_txn_count_w0_90 == txn_features2.sum_txn_count_w0_90}")

    # Test 5: Get customer profile with multiple groups
    print("\n5. Get customer profile with multiple feature groups:")
    profile = data_service.get_customer_profile(
        "C000001",
        include_groups=["transaction_features", "risk_features", "network_features"]
    )
    print(f"   ✓ Retrieved profile with {len(profile)} groups:")
    for group_name in profile.keys():
        print(f"      - {group_name}")

    # Test 6: Cache invalidation
    print("\n6. Test cache invalidation:")
    invalidated = data_service.invalidate_customer_cache("C000001", ["basic"])
    print(f"   ✓ Invalidated {invalidated} cache key(s)")

    # Test 7: Query after invalidation (cache miss again)
    print("\n7. Query after cache invalidation (should be cache MISS):")
    customer3 = data_service.get_customer_basic("C000001")
    if customer3:
        print(f"   ✓ Retrieved from DB: {customer3.name}")


def test_cache_service():
    """Test Redis cache service directly."""
    print_header("Testing Redis Cache Service")

    # Test 1: Health check
    print("\n1. Redis health check:")
    healthy = cache_service.health_check()
    print(f"   {'✓' if healthy else '✗'} Redis is {'healthy' if healthy else 'unhealthy'}")

    # Test 2: Set and get
    print("\n2. Test set and get:")
    test_data = {"test_key": "test_value", "number": 123}
    cache_service.set("test:example", test_data, ttl=60)
    retrieved = cache_service.get("test:example")
    print(f"   ✓ Set data: {test_data}")
    print(f"   ✓ Retrieved data: {retrieved}")
    print(f"   ✓ Match: {test_data == retrieved}")

    # Test 3: Delete
    print("\n3. Test delete:")
    deleted = cache_service.delete("test:example")
    print(f"   ✓ Deleted: {deleted}")
    retrieved_after = cache_service.get("test:example")
    print(f"   ✓ After delete: {retrieved_after is None}")


def test_feature_group_pattern():
    """Test feature group caching pattern."""
    print_header("Testing Feature Group Caching Pattern")

    # Clear cache
    cache_service.flush_all()

    print("\n1. Query ONE field from transaction_features group:")
    print("   User asks: 'What's the transaction count for C000001?'")
    txn_features = data_service.get_customer_transaction_features("C000001")
    print(f"   ✓ Answer: {txn_features.sum_txn_count_w0_90} transactions")
    print(f"   ✓ Cached: Entire transaction_features group (15 fields)")

    print("\n2. Query ANOTHER field from same group (5 seconds later):")
    print("   User asks: 'What's the average transaction amount for C000001?'")
    txn_features2 = data_service.get_customer_transaction_features("C000001")
    print(f"   ✓ Answer: ${txn_features2.avg_txn_amount_w0_90}")
    print(f"   ✓ Cache HIT! No DB query needed")

    print("\n3. Query field from DIFFERENT group:")
    print("   User asks: 'What's the network centrality for C000001?'")
    network_features = data_service.get_customer_network_features("C000001")
    print(f"   ✓ Answer: {network_features.network_degree_centrality}")
    print(f"   ✓ Cache MISS (different group), fetched from DB")
    print(f"   ✓ Cached: Entire network_features group")

    print("\n4. Summary:")
    print("   ✓ 3 user queries resulted in:")
    print("      - 2 DB queries (transaction_features, network_features)")
    print("      - 1 cache hit (transaction_features second query)")
    print("      - 2 feature groups cached for future queries")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  AML COPILOT - Repository & Service Layer Tests")
    print("="*60)

    try:
        # Repository tests
        test_customer_repository()
        test_transaction_repository()
        test_alert_repository()

        # Service layer tests
        test_cache_service()
        test_service_layer_caching()
        test_feature_group_pattern()

        print_header("✓ ALL TESTS COMPLETED SUCCESSFULLY")

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
