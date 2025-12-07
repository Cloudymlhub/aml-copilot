"""System test executor for boundary and error handling tests.

Executes tests that validate system robustness, error handling, and
boundary conditions.
"""

import time
from typing import Dict, Any
from datetime import datetime

from agents.state import AMLCopilotState
from evaluation.core.models import SystemTestCase, SystemTestResult
from evaluation.core.executors.base import BaseTestExecutor


class SystemTestExecutor(BaseTestExecutor):
    """Executor for system behavior test cases.

    Tests boundary handling, error handling, and system robustness
    using simple validation rules.
    """

    def execute(
        self,
        test_case: SystemTestCase,
        graph: Any
    ) -> SystemTestResult:
        """Execute a system test case.

        Args:
            test_case: System test case to execute
            graph: LangGraph compiled graph

        Returns:
            SystemTestResult with validation results
        """
        print(f"\n--- Test: {test_case.test_id} ---")
        print(f"Query: \"{test_case.input.user_query}\"")
        print(f"Expected: {test_case.description}")

        # Create initial state
        initial_state = self._create_initial_state(test_case)

        # Execute workflow
        start_time = time.time()
        try:
            # Invoke graph
            final_state = graph.invoke(initial_state)
            execution_time = time.time() - start_time

            # Extract output
            agent_output = {
                "final_response": final_state.get("final_response", ""),
                "compliance_analysis": final_state.get("compliance_analysis"),
                "completed": final_state.get("completed", False)
            }

            # Validate based on category
            validation_results = self._validate_output(final_state, test_case)

            # Determine status
            all_passed = all(validation_results.values())
            status = "PASS" if all_passed else "FAIL"

            # Create result
            result = SystemTestResult(
                test_id=test_case.test_id,
                test_type="system",
                status=status,
                agent_output=agent_output,
                validation_results=validation_results,
                execution_time_seconds=execution_time,
                timestamp=datetime.now()
            )

            # Print summary
            if status == "PASS":
                print(f"✅ PASS: {test_case.description}")
            else:
                print(f"❌ FAIL: {test_case.description}")
                for rule, passed in validation_results.items():
                    if not passed:
                        print(f"   Failed: {rule}")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"❌ ERROR: {str(e)}")

            return SystemTestResult(
                test_id=test_case.test_id,
                test_type="system",
                status="ERROR",
                agent_output={"error": str(e)},
                validation_results={},
                execution_time_seconds=execution_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )

    def _validate_output(
        self,
        state: AMLCopilotState,
        test_case: SystemTestCase
    ) -> Dict[str, bool]:
        """Validate output against rules.

        Args:
            state: Final state
            test_case: Test case with validation rules

        Returns:
            Dict mapping rule names to pass/fail
        """
        final_response = state.get("final_response", "").lower()
        compliance_analysis = state.get("compliance_analysis")
        validation_results = {}

        # Validate based on category
        if test_case.category == "off_topic":
            # Should decline gracefully
            decline_phrases = ["cannot", "unable", "outside", "scope", "help with aml"]
            has_decline = any(phrase in final_response for phrase in decline_phrases)
            no_analysis = not compliance_analysis

            validation_results["decline_off_topic"] = has_decline
            validation_results["no_analysis_for_off_topic"] = no_analysis

        elif test_case.category == "in_scope_general":
            # Should answer with analysis
            has_analysis = compliance_analysis is not None
            validation_results["provides_analysis"] = has_analysis

            # Check for expected terms from expected_output
            if test_case.expected_output and test_case.expected_output.response_includes:
                combined_text = f"{final_response} {str(compliance_analysis)}".lower()
                for term in test_case.expected_output.response_includes:
                    term_found = term.lower() in combined_text
                    validation_results[f"includes_{term}"] = term_found

        elif test_case.category == "error_handling":
            # Should handle gracefully (not crash)
            validation_results["completes_without_crash"] = True

            # Check for error handling response
            error_phrases = ["not found", "missing", "clarify", "provide"]
            handles_gracefully = any(phrase in final_response for phrase in error_phrases)
            validation_results["graceful_error_handling"] = handles_gracefully

        # Apply custom validation rules if provided
        for rule in test_case.validation_rules:
            if rule.validation_type == "contains":
                validation_results[rule.rule_name] = (
                    str(rule.expected_value).lower() in final_response
                )
            elif rule.validation_type == "not_contains":
                validation_results[rule.rule_name] = (
                    str(rule.expected_value).lower() not in final_response
                )

        return validation_results
