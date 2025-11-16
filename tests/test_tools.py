"""Test tools with sample queries."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import get_all_tools, CustomerDataTools, TransactionDataTools, AlertDataTools


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def test_tool_registry():
    """Test tool registry."""
    print_header("Testing Tool Registry")

    all_tools = get_all_tools()
    print(f"\n✓ Loaded {len(all_tools)} tools total")

    customer_tools = CustomerDataTools.get_tools()
    print(f"✓ Customer tools: {len(customer_tools)}")
    for tool in customer_tools:
        print(f"   - {tool.name}")

    transaction_tools = TransactionDataTools.get_tools()
    print(f"\n✓ Transaction tools: {len(transaction_tools)}")
    for tool in transaction_tools:
        print(f"   - {tool.name}")

    alert_tools = AlertDataTools.get_tools()
    print(f"\n✓ Alert tools: {len(alert_tools)}")
    for tool in alert_tools:
        print(f"   - {tool.name}")


def test_customer_tools():
    """Test customer data tools."""
    print_header("Testing Customer Data Tools")

    tools = CustomerDataTools.get_tools()

    # Test 1: Get customer basic info
    print("\n1. Get customer basic info for C000001:")
    basic_tool = next(t for t in tools if t.name == "get_customer_basic_info")
    result = basic_tool._run("C000001")
    if "error" not in result:
        print(f"   ✓ CIF: {result['cif_no']}")
        print(f"   ✓ Name: {result['name']}")
        print(f"   ✓ Risk Score: {result['risk_score']}")
        print(f"   ✓ Country: {result['country']}")
    else:
        print(f"   ✗ {result['error']}")

    # Test 2: Get transaction features
    print("\n2. Get transaction features for C000001:")
    txn_features_tool = next(t for t in tools if t.name == "get_customer_transaction_features")
    result = txn_features_tool._run("C000001")
    if "error" not in result:
        print(f"   ✓ Transaction count (0-30d): {result.get('sum_txn_count_w0_30', 'N/A')}")
        print(f"   ✓ Transaction count (0-90d): {result.get('sum_txn_count_w0_90', 'N/A')}")
        print(f"   ✓ Total amount (0-90d): ${result.get('sum_txn_amount_w0_90', 'N/A')}")
    else:
        print(f"   ✗ {result['error']}")

    # Test 3: Get risk features
    print("\n3. Get risk features for C000001:")
    risk_features_tool = next(t for t in tools if t.name == "get_customer_risk_features")
    result = risk_features_tool._run("C000001")
    if "error" not in result:
        print(f"   ✓ PEP: {result.get('is_pep', 'N/A')}")
        print(f"   ✓ Sanctions: {result.get('is_on_sanctions_list', 'N/A')}")
        print(f"   ✓ Adverse media: {result.get('adverse_media_mentions', 'N/A')}")
    else:
        print(f"   ✗ {result['error']}")

    # Test 4: Search by name
    print("\n4. Search customers by name 'John':")
    search_tool = next(t for t in tools if t.name == "search_customers_by_name")
    result = search_tool._run("John", limit=3)
    print(f"   ✓ Found {result['count']} customers")
    for customer in result['results'][:3]:
        print(f"      - {customer['cif_no']}: {customer['name']}")


def test_transaction_tools():
    """Test transaction data tools."""
    print_header("Testing Transaction Data Tools")

    tools = TransactionDataTools.get_tools()

    # Test 1: Get customer transactions
    print("\n1. Get transactions for C000001:")
    txn_tool = next(t for t in tools if t.name == "get_customer_transactions")
    result = txn_tool._run("C000001", limit=5)
    if "error" not in result:
        print(f"   ✓ Found {result['count']} transactions")
        if result['count'] > 0:
            txn = result['transactions'][0]
            print(f"      Latest: {txn['transaction_id']}")
            print(f"      Amount: ${txn['amount']} {txn['currency']}")
            print(f"      Date: {txn['transaction_date']}")
    else:
        print(f"   ✗ {result['error']}")

    # Test 2: Get high-risk transactions
    print("\n2. Get high-risk transactions for C000001:")
    high_risk_tool = next(t for t in tools if t.name == "get_high_risk_transactions")
    result = high_risk_tool._run("C000001", limit=5)
    if "error" not in result:
        print(f"   ✓ Found {result['count']} high-risk transactions")
        for txn in result['transactions'][:3]:
            flags = []
            if txn.get('is_cash_transaction'):
                flags.append("CASH")
            if txn.get('is_structured'):
                flags.append("STRUCTURED")
            if txn.get('is_high_risk_country'):
                flags.append("HIGH_RISK_COUNTRY")
            print(f"      - ${txn['amount']} [{', '.join(flags)}]")
    else:
        print(f"   ✗ {result['error']}")

    # Test 3: Get transaction count
    print("\n3. Get transaction count for C000001:")
    count_tool = next(t for t in tools if t.name == "get_transaction_count")
    result = count_tool._run("C000001")
    if "error" not in result:
        print(f"   ✓ Total transactions: {result['transaction_count']}")
    else:
        print(f"   ✗ {result['error']}")


def test_alert_tools():
    """Test alert data tools."""
    print_header("Testing Alert Data Tools")

    tools = AlertDataTools.get_tools()

    # Test 1: Get open alerts
    print("\n1. Get open alerts:")
    open_alerts_tool = next(t for t in tools if t.name == "get_open_alerts")
    result = open_alerts_tool._run(limit=5)
    print(f"   ✓ Found {result['count']} open alerts")
    for alert in result['alerts'][:3]:
        print(f"      - {alert['alert_id']}: {alert['alert_type']} [{alert['severity']}]")

    # Test 2: Get alerts by severity
    print("\n2. Get high severity alerts:")
    severity_tool = next(t for t in tools if t.name == "get_alerts_by_severity")
    result = severity_tool._run("high", limit=5)
    print(f"   ✓ Found {result['count']} high severity alerts")

    # Test 3: Get alerts by type
    print("\n3. Get structuring alerts:")
    type_tool = next(t for t in tools if t.name == "get_alerts_by_type")
    result = type_tool._run("structuring", limit=5)
    print(f"   ✓ Found {result['count']} structuring alerts")


def main():
    """Run all tool tests."""
    print("\n" + "="*60)
    print("  AML COPILOT - Tools Layer Tests")
    print("="*60)

    try:
        test_tool_registry()
        test_customer_tools()
        test_transaction_tools()
        test_alert_tools()

        print_header("✓ ALL TOOL TESTS COMPLETED SUCCESSFULLY")

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
