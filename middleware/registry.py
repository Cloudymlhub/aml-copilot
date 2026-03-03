"""Middleware registry for managing and applying middleware chains.

Provides a central registry for configuring and applying middleware to agents.
Supports conditional middleware application based on agent type or configuration.
"""

import logging
from typing import Any, Callable, List, Optional

from middleware.base import BaseMiddleware, MiddlewareContext, execute_with_middleware

logger = logging.getLogger(__name__)


class MiddlewareRegistry:
    """Registry for managing middleware chains.

    Allows configuring different middleware stacks for different agent types
    or execution contexts. Provides a clean interface for applying middleware.

    Example:
        # Set up registry
        registry = MiddlewareRegistry()
        registry.register_global(LoggingMiddleware())
        registry.register_global(CostTrackingMiddleware())
        registry.register_for_agent("AMLAlertReviewerAgent", AMLComplianceMiddleware())

        # Execute agent with middleware
        result = await registry.execute(
            agent_func=my_agent,
            agent_name="CoordinatorAgent",
            input_data=state,
            user_id="analyst_123",
        )
    """

    def __init__(self):
        """Initialize empty middleware registry."""
        self._global_middleware: List[BaseMiddleware] = []
        self._agent_middleware: dict[str, List[BaseMiddleware]] = {}
        self._enabled = True

    def register_global(self, middleware: BaseMiddleware) -> None:
        """Register middleware to apply to all agents.

        Args:
            middleware: Middleware instance to register globally
        """
        self._global_middleware.append(middleware)
        logger.debug(f"Registered global middleware: {type(middleware).__name__}")

    def register_for_agent(self, agent_name: str, middleware: BaseMiddleware) -> None:
        """Register middleware for specific agent type.

        Args:
            agent_name: Name of agent to apply middleware to
            middleware: Middleware instance to register
        """
        if agent_name not in self._agent_middleware:
            self._agent_middleware[agent_name] = []

        self._agent_middleware[agent_name].append(middleware)
        logger.debug(f"Registered middleware {type(middleware).__name__} for agent {agent_name}")

    def get_middleware_stack(self, agent_name: str) -> List[BaseMiddleware]:
        """Get complete middleware stack for an agent.

        Combines global middleware with agent-specific middleware.

        Args:
            agent_name: Name of the agent

        Returns:
            List of middleware in execution order (global first, then agent-specific)
        """
        if not self._enabled:
            return []

        stack = self._global_middleware.copy()

        # Add agent-specific middleware
        agent_specific = self._agent_middleware.get(agent_name, [])
        stack.extend(agent_specific)

        return stack

    async def execute(
        self,
        agent_func: Callable,
        agent_name: str,
        input_data: Any,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> Any:
        """Execute an agent with appropriate middleware stack.

        Args:
            agent_func: The agent function to execute
            agent_name: Name of the agent (for middleware selection)
            input_data: Input to pass to the agent
            user_id: User ID for audit trails
            session_id: Session ID for grouping executions
            execution_id: Optional execution ID (auto-generated if not provided)

        Returns:
            Output from the agent function

        Raises:
            Exception: Any exception raised by the agent
        """
        # Create execution context
        context = MiddlewareContext(
            agent_name=agent_name,
            execution_id=execution_id,
            user_id=user_id,
            session_id=session_id,
        )

        # Get middleware stack
        middleware_stack = self.get_middleware_stack(agent_name)

        if not middleware_stack:
            # No middleware - execute directly
            return await agent_func(input_data)

        # Execute with middleware chain
        return await execute_with_middleware(
            agent_func=agent_func,
            middleware_stack=middleware_stack,
            context=context,
            input_data=input_data,
        )

    def enable(self) -> None:
        """Enable middleware execution."""
        self._enabled = True
        logger.info("Middleware execution enabled")

    def disable(self) -> None:
        """Disable all middleware execution (for testing/debugging)."""
        self._enabled = False
        logger.warning("Middleware execution disabled")

    def clear(self) -> None:
        """Clear all registered middleware."""
        self._global_middleware.clear()
        self._agent_middleware.clear()
        logger.info("Cleared all registered middleware")

    def get_stats(self) -> dict:
        """Get statistics about registered middleware.

        Returns:
            Dict with middleware statistics
        """
        return {
            "enabled": self._enabled,
            "global_middleware_count": len(self._global_middleware),
            "agent_specific_count": len(self._agent_middleware),
            "total_agents_with_middleware": len(self._agent_middleware),
            "global_middleware": [type(m).__name__ for m in self._global_middleware],
            "agent_middleware": {
                agent: [type(m).__name__ for m in middleware]
                for agent, middleware in self._agent_middleware.items()
            },
        }


# Global singleton registry
_global_registry: Optional[MiddlewareRegistry] = None


def get_registry() -> MiddlewareRegistry:
    """Get the global middleware registry singleton.

    Returns:
        Global MiddlewareRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = MiddlewareRegistry()
    return _global_registry


def configure_default_middleware() -> MiddlewareRegistry:
    """Configure default middleware stack for AML Copilot.

    Sets up standard middleware:
    - LoggingMiddleware (global)
    - CostTrackingMiddleware (global)
    - AMLComplianceMiddleware (high-risk agents only)

    Returns:
        Configured MiddlewareRegistry
    """
    from middleware.aml_compliance_middleware import AMLComplianceMiddleware
    from middleware.cost_tracking_middleware import CostTrackingMiddleware
    from middleware.logging_middleware import LoggingMiddleware

    registry = get_registry()

    # Clear any existing middleware
    registry.clear()

    # Add global middleware
    registry.register_global(LoggingMiddleware(log_level=logging.INFO))
    registry.register_global(CostTrackingMiddleware(enable_cost_calculation=True))

    # Add compliance middleware for high-risk agents
    compliance_middleware = AMLComplianceMiddleware(log_high_risk_only=True)

    high_risk_agents = [
        "AMLAlertReviewerAgent",
        "SARNarrativeGenerator",
        "DispositionAgent",
    ]

    for agent_name in high_risk_agents:
        registry.register_for_agent(agent_name, compliance_middleware)

    logger.info("Configured default middleware stack")

    return registry
