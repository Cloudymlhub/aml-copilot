"""Conversation test executor for multi-turn conversation tests.

Executes multi-turn tests that evaluate message history, reference resolution,
and cross-turn data synthesis.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from agents.state import AMLCopilotState
from evaluation.core.models import (
    ConversationTestCase,
    ConversationTestResult,
    TurnResult,
    ConversationTurn
)
from evaluation.core.executors.base import BaseTestExecutor


class ConversationTestExecutor(BaseTestExecutor):
    """Executor for conversation/multi-turn test cases.

    Handles state accumulation across turns and validates cross-turn behavior.
    """

    def execute(
        self,
        test_case: ConversationTestCase,
        graph: Any
    ) -> ConversationTestResult:
        """Execute a conversation test case.

        Args:
            test_case: Conversation test case to execute
            graph: LangGraph compiled graph

        Returns:
            ConversationTestResult with turn-by-turn results
        """
        print(f"\n{'='*70}")
        print(f"Test: {test_case.test_id} - {test_case.description}")
        print(f"Category: {test_case.category}")
        print(f"Turns: {len(test_case.turns)}")
        print(f"{'='*70}")

        # Initialize state for conversation
        state = self._create_initial_state(test_case)
        turn_results: List[TurnResult] = []
        test_status = "PASS"
        error_message = None

        try:
            # Execute each turn
            for turn in test_case.turns:
                print(f"\n--- Turn {turn.turn_number} ---")
                print(f"Query: \"{turn.user_query}\"")

                # Execute turn
                state, turn_result = self._execute_turn(state, turn, graph)
                turn_results.append(turn_result)

                # Validate turn expectations
                turn_passed = self._validate_turn(state, turn, turn_result)

                if not turn_passed:
                    test_status = "FAIL"
                    turn_result.status = "FAIL"
                    print(f"❌ Turn {turn.turn_number} FAILED")
                else:
                    turn_result.status = "PASS"
                    print(f"✅ Turn {turn.turn_number} PASSED")

            # Validate overall success criteria
            if test_status == "PASS":
                if not self._validate_success_criteria(test_case, state, turn_results):
                    test_status = "FAIL"
                    error_message = "Success criteria not met"

        except Exception as e:
            test_status = "ERROR"
            error_message = str(e)
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

        # Create result
        result = ConversationTestResult(
            test_id=test_case.test_id,
            test_type="conversation",
            status=test_status,
            turn_results=turn_results,
            final_state=self._serialize_state(state),
            execution_time_seconds=sum(tr.validation_details.get("execution_time", 0) for tr in turn_results),
            timestamp=datetime.now(),
            error_message=error_message
        )

        # Print summary
        if test_status == "PASS":
            print(f"\n✅ TEST PASSED: {test_case.test_id}")
        elif test_status == "FAIL":
            print(f"\n❌ TEST FAILED: {test_case.test_id}")
            if error_message:
                print(f"   Reason: {error_message}")
        else:
            print(f"\n⚠️  TEST ERROR: {test_case.test_id}")
            print(f"   Error: {error_message}")

        return result

    def _execute_turn(
        self,
        state: AMLCopilotState,
        turn: ConversationTurn,
        graph: Any
    ) -> tuple[AMLCopilotState, TurnResult]:
        """Execute a single conversation turn.

        Args:
            state: Current state (accumulated from previous turns)
            turn: Turn definition
            graph: LangGraph compiled graph

        Returns:
            Tuple of (updated_state, turn_result)
        """
        import time

        # Update state for this turn
        state["user_query"] = turn.user_query
        state["next_agent"] = "coordinator"  # Always start turn at coordinator
        state["completed"] = False

        # Reset turn-specific fields (but preserve conversation context)
        state["current_step"] = "start"
        state["intent"] = None

        # Invoke graph for this turn
        start_time = time.time()
        final_state = graph.invoke(state)
        execution_time = time.time() - start_time

        # Build turn result
        turn_result = TurnResult(
            turn_number=turn.turn_number,
            query=turn.user_query,
            status="PENDING",  # Will be set after validation
            final_response=final_state.get("final_response", ""),
            retrieved_data=final_state.get("retrieved_data"),
            compliance_analysis=final_state.get("compliance_analysis"),
            intent=final_state.get("intent"),
            messages_count=len(final_state.get("messages", [])),
            current_step=final_state.get("current_step", ""),
            validation_details={"execution_time": execution_time}
        )

        return final_state, turn_result

    def _validate_turn(
        self,
        state: AMLCopilotState,
        turn: ConversationTurn,
        turn_result: TurnResult
    ) -> bool:
        """Validate a single turn's expectations.

        Args:
            state: Final state after turn execution
            turn: Turn definition with expected_behavior
            turn_result: Result dict for this turn

        Returns:
            True if turn passed all validations, False otherwise
        """
        expected = turn.expected_behavior
        if not expected:
            return True  # No expectations defined

        final_response = state.get("final_response", "").lower()
        retrieved_data = state.get("retrieved_data", {})

        # Check: Fetches data
        if expected.fetches_data is not None:
            data_fetched = retrieved_data and retrieved_data.get("success")
            if expected.fetches_data and not data_fetched:
                print(f"   ⚠️  Expected data fetch, but no data retrieved")
                return False

        # Check: Response includes expected terms
        if expected.response_includes:
            for term in expected.response_includes:
                if term.lower() not in final_response.lower():
                    print(f"   ⚠️  Response missing expected term: '{term}'")
                    return False

        # Check: Reference resolution
        if expected.resolves_reference:
            data_fetched = retrieved_data and retrieved_data.get("success")
            if not data_fetched:
                print(f"   ⚠️  Reference resolution likely failed - no data fetched")
                return False

        # Check: Cross-turn data reference
        if expected.references_turn_1_data:
            # Simple check: does response mention concepts from earlier data?
            mentions_customer = "customer" in final_response
            mentions_risk = "risk" in final_response
            if not (mentions_customer or mentions_risk):
                print(f"   ⚠️  Response doesn't reference expected data from previous turns")
                return False

        # Check: Cross-turn synthesis
        if expected.cross_turn_synthesis:
            # Count data types mentioned
            data_types_mentioned = 0
            if "customer" in final_response or "profile" in final_response:
                data_types_mentioned += 1
            if "transaction" in final_response:
                data_types_mentioned += 1
            if "risk" in final_response:
                data_types_mentioned += 1

            if data_types_mentioned < 2:
                print(f"   ⚠️  Insufficient synthesis: only {data_types_mentioned} data types mentioned")
                return False

        return True

    def _validate_success_criteria(
        self,
        test_case: ConversationTestCase,
        state: AMLCopilotState,
        turn_results: List[TurnResult]
    ) -> bool:
        """Validate overall conversation success criteria.

        Args:
            test_case: Test case with success criteria
            state: Final conversation state
            turn_results: Results from all turns

        Returns:
            True if all success criteria met, False otherwise
        """
        success_criteria = test_case.success_criteria

        # Check: All turns completed
        if success_criteria.all_turns_complete:
            if not all(turn.status in ["PASS", "PENDING"] for turn in turn_results):
                print("   ⚠️  Not all turns completed successfully")
                return False

        return True

    def _serialize_state(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Serialize state for storage in result.

        Args:
            state: AMLCopilotState to serialize

        Returns:
            Serialized state dict
        """
        # Convert to JSON-serializable dict
        return {
            "messages_count": len(state.get("messages", [])),
            "final_response": state.get("final_response"),
            "session_id": state.get("session_id"),
            "completed": state.get("completed", False)
        }

    def _validate_output(
        self,
        state: AMLCopilotState,
        test_case: ConversationTestCase
    ) -> Dict[str, Any]:
        """Validate output (satisfies abstract base requirement).

        For conversation tests, validation happens per-turn and in
        success criteria, so this returns an empty dict.

        Args:
            state: Final state
            test_case: Test case

        Returns:
            Empty validation dict
        """
        return {}
