"""Simple test runner for system tests without pytest dependency.

This script runs system tests and reports results.
"""

import json
import sys
from typing import Dict, Any
from datetime import datetime
import uuid
import traceback

from pathlib import Path

from agents.graph import create_aml_copilot_graph
from agents.state import AMLCopilotState
from config.settings import settings
from evaluation.config import (
    RESULTS_DIR,
    SYSTEM_TESTS_LATEST_FILE,
    get_result_file_path
)


def create_test_state(user_query: str, context: Dict[str, Any] = None) -> AMLCopilotState:
    """Create initial state for testing."""
    return {
        "messages": [],
        "user_query": user_query,
        "context": context or {},
        "next_agent": "coordinator",
        "current_step": "start",
        "intent": None,
        "retrieved_data": None,
        "compliance_analysis": None,
        "ml_model_output": None,
        "final_response": None,
        "review_status": None,
        "review_feedback": None,
        "additional_query": None,
        "review_agent_id": None,
        "review_attempts": 0,
        "session_id": f"test_{uuid.uuid4().hex[:8]}",
        "started_at": datetime.now().isoformat(),
        "completed": False
    }


def invoke_agent(graph, user_query: str, context: Dict[str, Any] = None) -> AMLCopilotState:
    """Invoke the agent with a query."""
    initial_state = create_test_state(user_query, context)
    final_state = graph.invoke(initial_state)
    return final_state


def run_boundary_tests():
    """Run boundary/off-topic handling tests."""
    print("\n" + "="*70)
    print("SYSTEM TESTS: Boundary / Off-Topic Handling")
    print("="*70)

    # Load test cases
    fixture_path = Path(__file__).parent / "fixtures" / "boundary_cases.json"
    with open(fixture_path, 'r') as f:
        test_cases = json.load(f)

    # Create agent graph
    config = settings.get_agents_config()
    graph = create_aml_copilot_graph(config)

    passed = 0
    failed = 0
    errors = 0

    # Run subset of critical tests
    test_ids_to_run = [
        "BOUNDARY_001",  # Weather question
        "BOUNDARY_002",  # General knowledge
        "BOUNDARY_003",  # Personal request (joke)
        "BOUNDARY_007",  # In-scope: What is structuring?
        "BOUNDARY_008",  # In-scope: CTR threshold
    ]

    for test_id in test_ids_to_run:
        test_case = next((tc for tc in test_cases if tc["test_id"] == test_id), None)
        if not test_case:
            continue

        print(f"\n--- Test: {test_id} ---")
        print(f"Query: \"{test_case['user_query']}\"")
        print(f"Expected: {test_case['description']}")

        try:
            # Invoke agent
            final_state = invoke_agent(graph, test_case["user_query"], test_case.get("context"))

            final_response = final_state.get("final_response", "").lower()
            compliance_analysis = final_state.get("compliance_analysis")

            # Evaluate based on expected behavior
            expected = test_case["expected_behavior"]

            if test_case["category"] == "off_topic":
                # Should decline
                decline_phrases = expected.get("decline_phrases", [])
                has_decline = any(phrase in final_response for phrase in decline_phrases)

                # Should not perform analysis
                no_analysis = not compliance_analysis

                if has_decline and no_analysis:
                    print("✅ PASS: Correctly declined off-topic question")
                    passed += 1
                else:
                    print(f"❌ FAIL: Did not properly decline")
                    print(f"   Has decline phrase: {has_decline}")
                    print(f"   No analysis: {no_analysis}")
                    print(f"   Response: {final_response[:200]}...")
                    failed += 1

            elif test_case["category"] == "in_scope_general":
                # Should answer
                should_answer = expected.get("should_answer", False)
                answer_should_include = expected.get("answer_should_include", [])

                has_analysis = compliance_analysis is not None
                combined_text = f"{final_response} {str(compliance_analysis)}".lower()

                includes_expected = all(
                    term.lower() in combined_text
                    for term in answer_should_include
                )

                if has_analysis and includes_expected:
                    print("✅ PASS: Correctly answered in-scope question")
                    passed += 1
                else:
                    print(f"❌ FAIL: Did not properly answer in-scope question")
                    print(f"   Has analysis: {has_analysis}")
                    print(f"   Includes expected terms: {includes_expected}")
                    failed += 1

        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            traceback.print_exc()
            errors += 1

    # Summary
    total = passed + failed + errors
    print(f"\n" + "="*70)
    print(f"BOUNDARY TESTS SUMMARY")
    print(f"="*70)
    print(f"Total: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")

    return passed, failed, errors


def run_error_handling_tests():
    """Run error handling tests."""
    print("\n" + "="*70)
    print("SYSTEM TESTS: Error Handling")
    print("="*70)

    # Load test cases
    fixture_path = Path(__file__).parent / "fixtures" / "error_handling_cases.json"
    with open(fixture_path, 'r') as f:
        test_cases = json.load(f)

    # Create agent graph
    config = settings.get_agents_config()
    graph = create_aml_copilot_graph(config)

    passed = 0
    failed = 0
    errors = 0

    # Run subset of critical tests
    test_ids_to_run = [
        "ERROR_001",  # Customer not found
        "ERROR_004",  # Missing context
    ]

    for test_id in test_ids_to_run:
        test_case = next((tc for tc in test_cases if tc["test_id"] == test_id), None)
        if not test_case:
            continue

        print(f"\n--- Test: {test_id} ---")
        print(f"Query: \"{test_case['user_query']}\"")
        print(f"Expected: {test_case['description']}")

        try:
            # Invoke agent
            final_state = invoke_agent(
                graph,
                test_case["user_query"],
                test_case.get("context")
            )

            # Should not crash
            if final_state is None:
                print("❌ FAIL: Agent crashed (returned None)")
                failed += 1
                continue

            final_response = final_state.get("final_response", "").lower()

            # Check expected behavior
            expected = test_case["expected_behavior"]

            if test_id == "ERROR_001":
                # Customer not found
                error_phrases = expected.get("error_message_should_include", [])
                has_error_message = any(phrase in final_response for phrase in error_phrases)

                if has_error_message:
                    print("✅ PASS: Gracefully handled missing customer")
                    passed += 1
                else:
                    print(f"❌ FAIL: Did not properly handle missing customer")
                    print(f"   Response: {final_response[:200]}...")
                    failed += 1

            elif test_id == "ERROR_004":
                # Missing context
                asks_clarification = any(phrase in final_response for phrase in [
                    "alert id", "which alert", "specify", "provide"
                ])

                if asks_clarification:
                    print("✅ PASS: Requested clarification for missing context")
                    passed += 1
                else:
                    print(f"❌ FAIL: Did not request clarification")
                    print(f"   Response: {final_response[:200]}...")
                    failed += 1

        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            traceback.print_exc()
            errors += 1

    # Summary
    total = passed + failed + errors
    if total > 0:
        print(f"\n" + "="*70)
        print(f"ERROR HANDLING TESTS SUMMARY")
        print(f"="*70)
        print(f"Total: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed}")
        print(f"Errors: {errors}")

    return passed, failed, errors


def main():
    """Run all system tests."""
    print("\n" + "="*70)
    print("AML COPILOT - SYSTEM TEST SUITE")
    print("="*70)

    try:
        # Run test suites
        boundary_results = run_boundary_tests()
        error_results = run_error_handling_tests()

        # Overall summary
        total_passed = boundary_results[0] + error_results[0]
        total_failed = boundary_results[1] + error_results[1]
        total_errors = boundary_results[2] + error_results[2]
        total = total_passed + total_failed + total_errors

        print(f"\n" + "="*70)
        print(f"OVERALL SYSTEM TEST SUMMARY")
        print(f"="*70)
        print(f"Total Tests: {total}")
        print(f"Passed: {total_passed} ({total_passed/total*100:.1f}%)")
        print(f"Failed: {total_failed}")
        print(f"Errors: {total_errors}")

        # Save results to JSON
        RESULTS_DIR.mkdir(exist_ok=True)

        results = {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": total_passed,
            "failed": total_failed,
            "errors": total_errors,
            "pass_rate": total_passed / total if total > 0 else 0.0,
            "category_stats": {
                "boundary_handling": {
                    "total": sum(boundary_results),
                    "passed": boundary_results[0],
                    "failed": boundary_results[1],
                    "errors": boundary_results[2]
                },
                "error_handling": {
                    "total": sum(error_results),
                    "passed": error_results[0],
                    "failed": error_results[1],
                    "errors": error_results[2]
                }
            }
        }

        # Save timestamped file
        results_file = get_result_file_path("system_tests", timestamped=True)
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        # Save as "latest"
        with open(SYSTEM_TESTS_LATEST_FILE, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n📊 Results saved to: {results_file}")
        print(f"📊 Latest results: {SYSTEM_TESTS_LATEST_FILE}")

        if total_failed == 0 and total_errors == 0:
            print(f"\n✅ All system tests passed!")
            return 0
        else:
            print(f"\n⚠️  Some tests failed or had errors")
            return 1

    except Exception as e:
        print(f"\n❌ Fatal error running system tests: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
