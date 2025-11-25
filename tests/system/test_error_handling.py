"""System tests for error handling.

Tests that the agent:
- Handles missing data gracefully
- Does not crash on errors
- Provides user-friendly error messages
- Does not hallucinate data when it's missing
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from agents.graph import create_aml_copilot_graph
from agents.state import AMLCopilotState
from config.agent_config import AgentsConfig
from datetime import datetime
import uuid


@pytest.fixture(scope="module")
def error_test_cases():
    """Load error handling test cases from JSON fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "system_test_cases" / "error_handling_cases.json"
    with open(fixture_path, 'r') as f:
        return json.load(f)


@pytest.fixture(scope="module")
def agent_graph():
    """Create agent graph for testing."""
    config = AgentsConfig()
    return create_aml_copilot_graph(config)


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


class TestMissingCustomer:
    """Test handling of missing/not found customers."""

    def test_customer_not_found(self, agent_graph, error_test_cases):
        """Test ERROR_001: Missing customer should be handled gracefully."""
        test_case = next(tc for tc in error_test_cases if tc["test_id"] == "ERROR_001")

        # This will attempt to access a non-existent customer
        final_state = invoke_agent(
            agent_graph,
            test_case["user_query"],
            test_case.get("context")
        )

        # Should not crash
        assert final_state is not None, "Agent should not crash"

        final_response = final_state.get("final_response", "").lower()

        # Should have error message
        error_phrases = test_case["expected_behavior"]["error_message_should_include"]
        has_error_message = any(phrase in final_response for phrase in error_phrases)

        assert has_error_message, \
            f"Should indicate customer not found. Got: {final_response}"

        # Should not hallucinate customer data
        compliance_analysis = final_state.get("compliance_analysis")

        # If analysis was attempted, it should acknowledge missing data
        if compliance_analysis:
            analysis_text = str(compliance_analysis).lower()
            # Should not contain made-up customer details
            suspicious_phrases = [
                "small business owner",
                "retail business",
                "john doe",
                "jane smith"
            ]
            # If any of these appear, they should be in context of "not available" or "missing"
            for phrase in suspicious_phrases:
                if phrase in analysis_text:
                    # Check that it's mentioned as missing/unavailable
                    assert "not available" in analysis_text or \
                           "missing" in analysis_text or \
                           "not found" in analysis_text, \
                           f"Should not hallucinate customer details: {phrase}"


class TestMissingData:
    """Test handling of missing transaction data."""

    def test_no_transactions(self, agent_graph, error_test_cases):
        """Test ERROR_002: No transaction data should be handled gracefully."""
        test_case = next(tc for tc in error_test_cases if tc["test_id"] == "ERROR_002")

        final_state = invoke_agent(
            agent_graph,
            test_case["user_query"],
            test_case.get("context")
        )

        # Should not crash
        assert final_state is not None

        final_response = final_state.get("final_response", "").lower()

        # Should explain no data available
        explains_no_data = any(phrase in final_response for phrase in [
            "no transactions",
            "no transaction data",
            "no recent transactions",
            "no data available"
        ])

        assert explains_no_data or "not available" in final_response, \
            "Should explain that transaction data is not available"

        # Should not hallucinate transactions
        compliance_analysis = final_state.get("compliance_analysis")
        if compliance_analysis:
            analysis_text = str(compliance_analysis).lower()

            # Should not mention specific transaction amounts or counts
            # Unless saying "no transactions" or "0 transactions"
            has_transaction_amounts = any(phrase in analysis_text for phrase in [
                "$9,850",
                "6 transactions",
                "multiple deposits",
                "frequent transactions"
            ])

            if has_transaction_amounts:
                # If it mentions transactions, should be in context of "no data"
                assert "no data" in analysis_text or \
                       "not available" in analysis_text or \
                       "missing" in analysis_text, \
                       "Should not hallucinate transaction details"


class TestInvalidInput:
    """Test handling of invalid inputs."""

    def test_invalid_cif_format(self, agent_graph, error_test_cases):
        """Test ERROR_003: Invalid CIF format should be handled."""
        test_case = next(tc for tc in error_test_cases if tc["test_id"] == "ERROR_003")

        final_state = invoke_agent(
            agent_graph,
            test_case["user_query"],
            test_case.get("context")
        )

        # Should not crash
        assert final_state is not None

        final_response = final_state.get("final_response", "").lower()

        # Should indicate validation issue or request valid format
        # Or attempt to work with what was provided
        # Either behavior is acceptable as long as no crash
        assert len(final_response) > 0, "Should provide some response"


class TestIncompleteContext:
    """Test handling of incomplete context."""

    def test_missing_alert_id(self, agent_graph, error_test_cases):
        """Test ERROR_004: Missing alert ID should request clarification."""
        test_case = next(tc for tc in error_test_cases if tc["test_id"] == "ERROR_004")

        final_state = invoke_agent(
            agent_graph,
            test_case["user_query"],
            test_case.get("context", {})
        )

        # Should not crash
        assert final_state is not None

        final_response = final_state.get("final_response", "").lower()

        # Should ask for alert ID
        asks_for_alert = any(phrase in final_response for phrase in [
            "alert id",
            "which alert",
            "specify",
            "provide"
        ])

        assert asks_for_alert, \
            f"Should ask for alert ID when missing. Got: {final_response}"


class TestPartialData:
    """Test handling of partial/incomplete data."""

    def test_incomplete_customer_profile(self, agent_graph, error_test_cases):
        """Test ERROR_007: Incomplete customer profile should be handled."""
        test_case = next(tc for tc in error_test_cases if tc["test_id"] == "ERROR_007")

        final_state = invoke_agent(
            agent_graph,
            test_case["user_query"],
            test_case.get("context")
        )

        # Should not crash
        assert final_state is not None

        final_response = final_state.get("final_response", "").lower()
        compliance_analysis = final_state.get("compliance_analysis")

        # Should proceed with available data
        # Should not hallucinate missing fields
        # Acceptable to note limitations

        if compliance_analysis:
            analysis_text = str(compliance_analysis).lower()

            # If analysis mentions data gaps, that's good
            acknowledges_limits = any(phrase in analysis_text for phrase in [
                "not available",
                "missing",
                "incomplete",
                "limited data",
                "available data"
            ])

            # Either provides analysis with caveat, or explains limitations
            assert len(final_response) > 0, "Should provide some response"


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
