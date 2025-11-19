"""Test the multi-agent AML Copilot system."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.copilot import AMLCopilot


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def print_response(result: dict):
    """Print agent response in formatted way."""
    print("\n" + "─" * 70)
    print("FINAL RESPONSE:")
    print("─" * 70)
    print(result.get("response", "No response"))
    print("─" * 70)

    # Print agent trace
    messages = result.get("messages", [])
    if len(messages) > 1:
        print("\nAGENT TRACE:")
        for msg in messages[1:]:  # Skip user message
            if msg["role"] == "assistant":
                print(f"  {msg['content']}")

    # Print compliance analysis if available
    compliance = result.get("compliance_analysis")
    if compliance:
        print("\nCOMPLIANCE ANALYSIS:")
        if compliance.get("typologies"):
            print(f"  Typologies: {', '.join(compliance['typologies'])}")
        if compliance.get("recommendations"):
            print(f"  Recommendations: {len(compliance['recommendations'])} items")


def test_basic_customer_query():
    """Test basic customer data query."""
    print_header("Test 1: Basic Customer Query")

    copilot = AMLCopilot()

    query = "What is the risk score for customer C000001?"
    print(f"\nQuery: {query}")

    result = copilot.query(query)
    print_response(result)


def test_transaction_query():
    """Test transaction query."""
    print_header("Test 2: Transaction Query")

    copilot = AMLCopilot()

    query = "Show me the high-risk transactions for customer C000001"
    print(f"\nQuery: {query}")

    result = copilot.query(query)
    print_response(result)


def test_compliance_question():
    """Test pure compliance question."""
    print_header("Test 3: Compliance Question (No Data Needed)")

    copilot = AMLCopilot()

    query = "What is structuring and how do I identify it?"
    print(f"\nQuery: {query}")

    result = copilot.query(query)
    print_response(result)


def test_mixed_query():
    """Test mixed query requiring data + analysis."""
    print_header("Test 4: Mixed Query (Data + Analysis)")

    copilot = AMLCopilot()

    query = "Analyze the AML risk for customer C000001 based on their transaction patterns"
    print(f"\nQuery: {query}")

    result = copilot.query(query)
    print_response(result)


def test_alert_query():
    """Test alert query."""
    print_header("Test 5: Alert Query")

    copilot = AMLCopilot()

    query = "Show me all open high severity alerts"
    print(f"\nQuery: {query}")

    result = copilot.query(query)
    print_response(result)


def main():
    """Run all agent tests."""
    print("\n" + "="*70)
    print("  AML COPILOT - Multi-Agent System Tests")
    print("="*70)

    try:
        # Run tests
        test_basic_customer_query()
        test_transaction_query()
        test_compliance_question()
        test_mixed_query()
        test_alert_query()

        print_header("✓ ALL AGENT TESTS COMPLETED")

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
