"""Base middleware class for AML Copilot agent system.

Middleware wraps agent execution to provide cross-cutting concerns like:
- Logging and observability
- Cost tracking and token usage
- Audit trails for compliance
- Performance monitoring
- Error handling

All middleware must inherit from BaseMiddleware and implement the before/after hooks.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from uuid import uuid4


class MiddlewareContext:
    """Context object passed through middleware chain.

    Contains execution metadata and allows middleware to share state.
    """

    def __init__(
        self,
        agent_name: str,
        execution_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Initialize middleware context.

        Args:
            agent_name: Name of the agent being executed
            execution_id: Unique ID for this execution (auto-generated if not provided)
            user_id: ID of the user initiating the request (for audit trails)
            session_id: Session/conversation ID (for grouping related executions)
        """
        self.agent_name = agent_name
        self.execution_id = execution_id or str(uuid4())
        self.user_id = user_id
        self.session_id = session_id
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        self.metadata: Dict[str, Any] = {}
        self.error: Optional[Exception] = None

    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()


class BaseMiddleware(ABC):
    """Abstract base class for all middleware.

    Middleware follows the Chain of Responsibility pattern, wrapping agent execution
    with before/after hooks. Middleware is composable and can be stacked.

    Example:
        class LoggingMiddleware(BaseMiddleware):
            async def before_execute(self, context: MiddlewareContext, input_data: Any) -> None:
                print(f"Starting {context.agent_name}")

            async def after_execute(self, context: MiddlewareContext, output_data: Any) -> None:
                print(f"Completed {context.agent_name} in {context.duration_seconds()}s")
    """

    @abstractmethod
    async def before_execute(
        self,
        context: MiddlewareContext,
        input_data: Any,
    ) -> None:
        """Hook called before agent execution.

        Use this for:
        - Logging execution start
        - Validating inputs
        - Setting up context/state
        - Starting timers/metrics

        Args:
            context: Execution context with metadata
            input_data: Input being passed to the agent (e.g., AMLCopilotState)

        Raises:
            Exception: Can raise to abort execution before agent runs
        """
        pass

    @abstractmethod
    async def after_execute(
        self,
        context: MiddlewareContext,
        output_data: Any,
    ) -> None:
        """Hook called after agent execution completes.

        Use this for:
        - Logging execution results
        - Recording metrics/costs
        - Saving audit trails
        - Cleanup

        Args:
            context: Execution context with metadata (includes error if failed)
            output_data: Output returned by the agent (None if error occurred)

        Note:
            This is called even if the agent raised an exception.
            Check context.error to see if execution failed.
        """
        pass

    async def on_error(
        self,
        context: MiddlewareContext,
        error: Exception,
    ) -> None:
        """Hook called when agent execution fails.

        Default implementation does nothing. Override for custom error handling.

        Args:
            context: Execution context with metadata
            error: The exception that was raised
        """
        pass


async def execute_with_middleware(
    agent_func: Callable,
    middleware_stack: list[BaseMiddleware],
    context: MiddlewareContext,
    input_data: Any,
) -> Any:
    """Execute an agent function with middleware chain.

    Runs all before_execute hooks, executes the agent, then runs all after_execute hooks.
    Ensures after_execute is called even if execution fails.

    Args:
        agent_func: The agent function to execute
        middleware_stack: List of middleware to apply (in order)
        context: Execution context
        input_data: Input to pass to the agent

    Returns:
        Output from the agent function

    Raises:
        Exception: Any exception raised by the agent (after running all after_execute hooks)
    """
    output_data = None

    try:
        # Run all before hooks
        for middleware in middleware_stack:
            await middleware.before_execute(context, input_data)

        # Execute the agent
        output_data = await agent_func(input_data)

        return output_data

    except Exception as e:
        # Record error in context
        context.error = e

        # Run error hooks
        for middleware in middleware_stack:
            try:
                await middleware.on_error(context, e)
            except Exception:
                # Don't let middleware error handling break the chain
                pass

        raise

    finally:
        # Record end time
        context.end_time = datetime.utcnow()

        # Run all after hooks (even if execution failed)
        for middleware in middleware_stack:
            try:
                await middleware.after_execute(context, output_data)
            except Exception:
                # Don't let middleware cleanup break the chain
                pass
