#!/usr/bin/env python3
"""
Phase 2 Test Runner: PEAR Loop and Advanced Agent Interactions

Tests:
- Test 2.1: Review Agent - needs_data (Full Replan)
- Test 2.2: Review Agent - needs_refinement (Partial Retry)
- Test 1.5: Intent Mapper - Multiple Tool Selection
- Test 1.6: Intent Mapper - Ambiguous Query Handling

Usage:
    python run_tests_phase2.py
"""

import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional

BASE_URL = "http://localhost:8000"

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}ℹ {text}{RESET}")


def make_query(
    query: str,
    cif_no: str = "C000001",
    session_id: Optional[str] = None,
    user_id: str = "test_analyst"
) -> Dict[str, Any]:
    """Make a query to the API.

    Args:
        query: The query string
        cif_no: Customer ID
        session_id: Session ID (auto-generated if None)
        user_id: User ID

    Returns:
        Response data dictionary
    """
    if session_id is None:
        session_id = f"test_phase2_{datetime.now().strftime('%H%M%S%f')}"

    payload = {
        "query": query,
        "context": {"cif_no": cif_no},
        "user_id": user_id,
        "session_id": session_id
    }

    try:
        response = requests.post(f"{BASE_URL}/api/query", json=payload, timeout=180)

        if response.status_code == 200:
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json()
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def test_2_1_needs_data():
    """Test 2.1: Review Agent - needs_data (Full Replan)

    Trigger: Query that can be partially answered but Review Agent determines needs more data
    Expected: Review sets needs_data, routes back to Intent Mapper for additional data
    """
    print_header("Test 2.1: Review Agent - needs_data (Full Replan)")

    print_info("Objective: Trigger Review Agent to request additional data via PEAR loop")
    print_info("Expected: Review Agent sets review_status='needs_data', routes to Intent Mapper")

    # Query that mentions analysis but doesn't specify what data to include
    query = "Provide a comprehensive AML risk analysis for this customer"
    print(f"\nQuery: {query}")
    print(f"Customer: C000001")

    result = make_query(query, cif_no="C000001")

    if result["success"]:
        data = result["data"]
        response = data.get("response", "")

        print(f"\n{GREEN}Status: {result['status_code']} OK{RESET}")
        print(f"\nResponse Preview:\n{response[:500]}...")

        # Check if compliance analysis was performed
        if data.get("compliance_analysis"):
            print_success("Compliance analysis generated")
            ca = data["compliance_analysis"]
            if ca.get("risk_assessment"):
                print(f"  Risk Assessment: {ca['risk_assessment']}")
            if ca.get("typologies"):
                print(f"  Typologies: {ca['typologies']}")

        # Check if data was retrieved
        if data.get("retrieved_data"):
            print_success(f"Data retrieved: {len(data['retrieved_data'])} fields")

        # Note: We can't directly see review_status from the final response
        # but we can infer PEAR loop execution by checking if comprehensive data was gathered
        print_success("TEST 2.1 COMPLETED - Check if comprehensive data was gathered")
        return True
    else:
        print_error(f"Request failed: {result.get('error', 'Unknown error')}")
        print_error("TEST 2.1 FAILED")
        return False


def test_2_2_needs_refinement():
    """Test 2.2: Review Agent - needs_refinement (Partial Retry)

    Trigger: Query where initial analysis might be too generic
    Expected: Review Agent requests refinement, routes back to Compliance Expert
    """
    print_header("Test 2.2: Review Agent - needs_refinement (Partial Retry)")

    print_info("Objective: Trigger Review Agent to request better analysis")
    print_info("Expected: Review Agent sets review_status='needs_refinement', routes to Compliance Expert")

    # Query requesting specific analysis that might need refinement
    query = "What specific AML red flags should I look for with this customer?"
    print(f"\nQuery: {query}")
    print(f"Customer: C000001")

    result = make_query(query, cif_no="C000001")

    if result["success"]:
        data = result["data"]
        response = data.get("response", "")

        print(f"\n{GREEN}Status: {result['status_code']} OK{RESET}")
        print(f"\nResponse Preview:\n{response[:500]}...")

        # Check for specific AML red flags in response
        response_lower = response.lower()
        red_flag_indicators = [
            "red flag" in response_lower,
            "warning sign" in response_lower,
            "indicator" in response_lower,
            "suspicious" in response_lower,
            "pattern" in response_lower
        ]

        if any(red_flag_indicators):
            print_success("Response includes specific red flag analysis")

        # Check compliance analysis
        if data.get("compliance_analysis"):
            ca = data["compliance_analysis"]
            if ca.get("recommendations"):
                print_success(f"Recommendations provided: {len(ca['recommendations'])} items")
                for i, rec in enumerate(ca['recommendations'][:3], 1):
                    print(f"  {i}. {rec}")

        print_success("TEST 2.2 COMPLETED - Check for specific red flag analysis")
        return True
    else:
        print_error(f"Request failed: {result.get('error', 'Unknown error')}")
        print_error("TEST 2.2 FAILED")
        return False


def test_1_5_multiple_tool_selection():
    """Test 1.5: Intent Mapper - Multiple Tool Selection

    Trigger: Query explicitly requesting multiple data points
    Expected: Intent Mapper selects multiple tools, all data retrieved
    """
    print_header("Test 1.5: Intent Mapper - Multiple Tool Selection")

    print_info("Objective: Verify Intent Mapper can select and execute multiple tools")
    print_info("Expected: Multiple tools selected via bind_tools, all data retrieved")

    # Query asking for multiple distinct data points
    query = "Show me the customer's basic information, their transaction history, and risk assessment"
    print(f"\nQuery: {query}")
    print(f"Customer: C000001")

    result = make_query(query, cif_no="C000001")

    if result["success"]:
        data = result["data"]
        response = data.get("response", "")

        print(f"\n{GREEN}Status: {result['status_code']} OK{RESET}")
        print(f"\nResponse Preview:\n{response[:500]}...")

        # Check if multiple data types were retrieved
        retrieved = data.get("retrieved_data", {})
        if retrieved:
            print_success(f"Data retrieved: {len(retrieved)} fields")

            # Check for different data categories
            data_categories = []
            if any(k in retrieved for k in ["customer_name", "account_open_date", "occupation"]):
                data_categories.append("Basic Info")
            if any(k in retrieved for k in ["transactions", "transaction_count"]):
                data_categories.append("Transactions")
            if any(k in retrieved for k in ["risk_score", "risk_level"]):
                data_categories.append("Risk Assessment")

            if len(data_categories) >= 2:
                print_success(f"Multiple data categories retrieved: {', '.join(data_categories)}")
            else:
                print_warning(f"Only {len(data_categories)} data category retrieved")

        print_success("TEST 1.5 COMPLETED - Check multiple data categories")
        return True
    else:
        print_error(f"Request failed: {result.get('error', 'Unknown error')}")
        print_error("TEST 1.5 FAILED")
        return False


def test_1_6_ambiguous_query():
    """Test 1.6: Intent Mapper - Ambiguous Query Handling

    Trigger: Very vague query lacking context
    Expected: System requests clarification or makes reasonable interpretation
    """
    print_header("Test 1.6: Intent Mapper - Ambiguous Query Handling")

    print_info("Objective: Test handling of ambiguous/vague queries")
    print_info("Expected: Clarification request OR reasonable interpretation with caveats")

    # Intentionally vague query
    query = "Tell me about the customer"
    print(f"\nQuery: {query}")
    print(f"Customer: C000001")

    result = make_query(query, cif_no="C000001")

    if result["success"]:
        data = result["data"]
        response = data.get("response", "")

        print(f"\n{GREEN}Status: {result['status_code']} OK{RESET}")
        print(f"\nResponse Preview:\n{response[:500]}...")

        # Check if response handles ambiguity appropriately
        response_lower = response.lower()

        # Look for clarification language
        clarification_indicators = [
            "clarify" in response_lower,
            "specific" in response_lower,
            "which" in response_lower,
            "more information" in response_lower,
            "could you" in response_lower
        ]

        # Look for reasonable interpretation
        interpretation_indicators = [
            "summary" in response_lower,
            "overview" in response_lower,
            "general" in response_lower,
            "basic information" in response_lower
        ]

        if any(clarification_indicators):
            print_success("Response requests clarification")
        elif any(interpretation_indicators):
            print_success("Response provides reasonable interpretation")
            if data.get("retrieved_data"):
                print_success("Basic data retrieved as fallback")

        print_success("TEST 1.6 COMPLETED - Check ambiguity handling")
        return True
    else:
        print_error(f"Request failed: {result.get('error', 'Unknown error')}")
        print_error("TEST 1.6 FAILED")
        return False


def run_phase_2_tests():
    """Run all Phase 2 tests."""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}AML Copilot - Phase 2 Test Suite{RESET}")
    print(f"{BLUE}PEAR Loop and Advanced Agent Interactions{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")

    print(f"\n{YELLOW}Prerequisites:{RESET}")
    print("  1. API running at http://localhost:8000")
    print("  2. Database seeded with test data")
    print("  3. Redis running")

    # Health check
    print_info("\nPerforming health check...")
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5).json()
        if health.get("status") == "healthy":
            print_success("API is healthy")
        else:
            print_warning(f"API status: {health.get('status')}")
    except Exception as e:
        print_error(f"Health check failed: {e}")
        print_error("Please ensure API is running: make api-run")
        return

    # Run tests
    results = {}

    print(f"\n{BLUE}Starting Phase 2 Tests...{RESET}\n")

    results["2.1"] = test_2_1_needs_data()
    print()

    results["2.2"] = test_2_2_needs_refinement()
    print()

    results["1.5"] = test_1_5_multiple_tool_selection()
    print()

    results["1.6"] = test_1_6_ambiguous_query()
    print()

    # Summary
    print_header("Phase 2 Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests completed")
    print()

    for test_id, result in results.items():
        status = f"{GREEN}✓ PASS{RESET}" if result else f"{RED}✗ FAIL{RESET}"
        print(f"  Test {test_id}: {status}")

    if passed == total:
        print(f"\n{GREEN}{'='*80}{RESET}")
        print(f"{GREEN}All Phase 2 tests completed successfully!{RESET}")
        print(f"{GREEN}{'='*80}{RESET}")
    else:
        print(f"\n{YELLOW}{'='*80}{RESET}")
        print(f"{YELLOW}Phase 2 tests completed with {total - passed} issue(s){RESET}")
        print(f"{YELLOW}{'='*80}{RESET}")

    print(f"\n{BLUE}Note:{RESET} Phase 2 focuses on advanced agent interactions.")
    print("Some behaviors (like PEAR loop triggering) may be difficult to observe")
    print("from the final response. Review agent logs for detailed execution flow.")


if __name__ == "__main__":
    run_phase_2_tests()
