"""Middleware framework for AML Copilot agent system.

This package provides middleware for cross-cutting concerns in agent execution:

- Logging: Structured execution logging
- Cost Tracking: Token usage and cost monitoring
- Compliance: Audit trails for regulatory requirements
- Registry: Middleware orchestration and management

Usage:
    from middleware import configure_default_middleware, get_registry

    # Set up default middleware
    registry = configure_default_middleware()

    # Execute agent with middleware
    result = await registry.execute(
        agent_func=my_agent,
        agent_name="CoordinatorAgent",
        input_data=state,
        user_id="analyst_123",
    )

Custom middleware:
    from middleware import BaseMiddleware, MiddlewareContext, get_registry

    class CustomMiddleware(BaseMiddleware):
        async def before_execute(self, context: MiddlewareContext, input_data: Any) -> None:
            # Custom logic before agent execution
            pass

        async def after_execute(self, context: MiddlewareContext, output_data: Any) -> None:
            # Custom logic after agent execution
            pass

    # Register custom middleware
    registry = get_registry()
    registry.register_global(CustomMiddleware())
"""

from middleware.aml_compliance_middleware import AMLComplianceMiddleware
from middleware.base import BaseMiddleware, MiddlewareContext, execute_with_middleware
from middleware.cost_tracking_middleware import CostTrackingMiddleware
from middleware.logging_middleware import LoggingMiddleware
from middleware.registry import MiddlewareRegistry, configure_default_middleware, get_registry

__all__ = [
    # Base classes
    "BaseMiddleware",
    "MiddlewareContext",
    "execute_with_middleware",
    # Middleware implementations
    "LoggingMiddleware",
    "CostTrackingMiddleware",
    "AMLComplianceMiddleware",
    # Registry
    "MiddlewareRegistry",
    "get_registry",
    "configure_default_middleware",
]
