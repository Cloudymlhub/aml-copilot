"""Base executor for all test types.

Provides abstract base class that all executors must implement, along with
shared utility methods for state creation and execution.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from agents.state import AMLCopilotState
from evaluation.core.models import BaseTestCase, BaseTestResult


class BaseTestExecutor(ABC):
    """Abstract base class for test executors.

    All test type executors (Golden, Conversation, System) inherit from this
    and implement the execute() and _validate_output() methods.

    The base class provides shared functionality for:
    - State initialization (DRY - eliminates duplication)
    - Common execution patterns
    - Error handling
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize executor.

        Args:
            config: Test-type-specific configuration (timeouts, max_turns, etc.)
        """
        self.config = config or {}

    @abstractmethod
    def execute(
        self,
        test_case: BaseTestCase,
        graph: Any  # CompiledGraph type
    ) -> BaseTestResult:
        """Execute a test case and return result.

        This is the main entry point that each executor must implement.

        NOTE: This method runs the test (invokes the graph).
        Evaluation (scoring) is done separately by UnifiedTestRunner
        calling execute.evaluate() for each evaluator.

        Args:
            test_case: Test case to execute
            graph: LangGraph compiled graph

        Returns:
            Test result (specific subclass of BaseTestResult)
        """
        pass

    def evaluate(
        self,
        evaluator: Any,
        evaluator_config: Dict[str, Any],
        test_case: BaseTestCase,
        agent_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate using injected evaluator strategy.

        This method implements the strategy pattern:
        - Executor receives evaluator + config as parameters
        - Executor is stateless (no evaluator ownership)
        - Config is auto-loaded from YAML by Pydantic validator

        Args:
            evaluator: Evaluator instance (strategy)
            evaluator_config: Evaluator-specific config (auto-loaded from YAML)
            test_case: Test case with expected outputs
            agent_output: Actual agent output to evaluate

        Returns:
            Evaluation result with score

        Example:
            >>> executor = GoldenTestExecutor()
            >>> evaluator = CorrectnessEvaluator()
            >>> config = {"typologies": {"weight": 0.4}, ...}
            >>> result = executor.evaluate(
            ...     evaluator=evaluator,
            ...     evaluator_config=config,
            ...     test_case=test_case,
            ...     agent_output={"final_response": "..."}
            ... )
            >>> result["score"]
            0.85
        """
        # Optional: Configure evaluator if it supports dynamic configuration
        if hasattr(evaluator, "configure"):
            evaluator.configure(evaluator_config)

        # Call evaluator with test case expectations
        return evaluator.evaluate(
            agent_output=agent_output,
            expected_output=test_case.expected_output,
            criteria=test_case.evaluation_criteria
        )

    def _create_initial_state(
        self,
        test_case: BaseTestCase,
        user_query: Optional[str] = None
    ) -> AMLCopilotState:
        """Create initial state from test case.

        This is a shared implementation that eliminates the duplication that
        currently exists across the 3 separate test runners.

        Args:
            test_case: Test case to create state for
            user_query: User query (defaults to test_case.input.user_query)

        Returns:
            Initial AMLCopilotState ready for graph execution
        """
        return {
            "messages": [],
            "user_query": user_query or test_case.input.user_query,
            "context": test_case.input.context,
            "next_agent": "coordinator",
            "current_step": "start",
            "intent": None,
            "retrieved_data": None,
            "compliance_analysis": None,
            "ml_model_output": test_case.input.ml_output,
            "final_response": None,
            "review_status": None,
            "review_feedback": None,
            "additional_query": None,
            "review_agent_id": None,
            "review_attempts": 0,
            "session_id": f"test_{test_case.test_id}_{uuid.uuid4().hex[:8]}",
            "started_at": datetime.now().isoformat(),
            "completed": False,
        }

    @abstractmethod
    def _validate_output(
        self,
        state: AMLCopilotState,
        test_case: BaseTestCase
    ) -> Dict[str, Any]:
        """Validate output against expected behavior.

        Each executor implements its own validation logic.

        Args:
            state: Final state after execution
            test_case: Original test case with expected output

        Returns:
            Dictionary with validation results
        """
        pass

    def _get_timeout(self) -> int:
        """Get timeout in seconds from config.

        Returns:
            Timeout in seconds (default: 60)
        """
        return self.config.get("timeout_seconds", 60)
