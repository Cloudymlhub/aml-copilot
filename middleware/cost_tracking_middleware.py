"""Cost tracking middleware for LLM token usage monitoring.

Tracks token consumption and costs across agent executions to:
- Monitor API usage and costs
- Identify expensive operations
- Set budget alerts
- Optimize prompts and agent design
"""

import logging
from typing import Any, Optional

from middleware.base import BaseMiddleware, MiddlewareContext

logger = logging.getLogger(__name__)


class CostTrackingMiddleware(BaseMiddleware):
    """Middleware for tracking LLM token usage and costs.

    Extracts token usage from LLM responses and calculates costs based on
    model pricing. Logs usage metrics for monitoring and optimization.
    """

    # Token costs per 1M tokens (as of Dec 2024)
    # Update these when pricing changes
    TOKEN_COSTS = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.150, "output": 0.600},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        # Claude models (for reference, not used currently)
        "claude-opus-4": {"input": 15.00, "output": 75.00},
        "claude-sonnet-3.5": {"input": 3.00, "output": 15.00},
    }

    def __init__(self, enable_cost_calculation: bool = True, warn_threshold_dollars: Optional[float] = None):
        """Initialize cost tracking middleware.

        Args:
            enable_cost_calculation: Whether to calculate costs (requires model info)
            warn_threshold_dollars: Log warning if single execution exceeds this cost
        """
        self.enable_cost_calculation = enable_cost_calculation
        self.warn_threshold_dollars = warn_threshold_dollars

    async def before_execute(
        self,
        context: MiddlewareContext,
        input_data: Any,
    ) -> None:
        """Initialize token tracking in context."""
        context.metadata["token_usage"] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "model": None,
            "cost_dollars": 0.0,
        }

    async def after_execute(
        self,
        context: MiddlewareContext,
        output_data: Any,
    ) -> None:
        """Extract token usage from output and log costs."""
        # Extract token usage from output
        usage = self._extract_usage(output_data, context)

        if usage:
            context.metadata["token_usage"].update(usage)

            # Calculate cost if enabled
            if self.enable_cost_calculation and usage.get("model"):
                cost = self._calculate_cost(usage)
                context.metadata["token_usage"]["cost_dollars"] = cost

                # Log cost metrics
                self._log_usage(context, usage, cost)

                # Warn if exceeds threshold
                if self.warn_threshold_dollars and cost > self.warn_threshold_dollars:
                    logger.warning(
                        f"High cost execution: ${cost:.4f} for {context.agent_name}",
                        extra={
                            "event": "high_cost_execution",
                            "execution_id": context.execution_id,
                            "agent_name": context.agent_name,
                            "cost_dollars": cost,
                            "threshold_dollars": self.warn_threshold_dollars,
                            "token_usage": usage,
                        },
                    )

    def _extract_usage(self, output_data: Any, context: MiddlewareContext) -> Optional[dict]:
        """Extract token usage from agent output.

        Supports multiple output formats:
        - LangChain AIMessage with usage_metadata
        - Dict with 'usage' or 'token_usage' key
        - AgentResponse with usage info

        Args:
            output_data: Output from agent
            context: Execution context

        Returns:
            Dict with token usage info or None
        """
        if output_data is None:
            return None

        usage = {}

        # Try to extract from LangChain AIMessage
        if hasattr(output_data, "usage_metadata"):
            metadata = output_data.usage_metadata
            usage = {
                "input_tokens": metadata.get("input_tokens", 0),
                "output_tokens": metadata.get("output_tokens", 0),
                "total_tokens": metadata.get("total_tokens", 0),
            }

        # Try to extract from dict-like response
        elif hasattr(output_data, "get") or isinstance(output_data, dict):
            data_dict = dict(output_data) if not isinstance(output_data, dict) else output_data

            # Check for usage key
            if "usage" in data_dict:
                usage_data = data_dict["usage"]
                usage = {
                    "input_tokens": usage_data.get("prompt_tokens", 0),
                    "output_tokens": usage_data.get("completion_tokens", 0),
                    "total_tokens": usage_data.get("total_tokens", 0),
                }

            # Check for token_usage key
            elif "token_usage" in data_dict:
                usage = data_dict["token_usage"]

        # Try to extract model info from context or output
        if usage:
            # Look for model in output
            if hasattr(output_data, "response_metadata"):
                usage["model"] = output_data.response_metadata.get("model_name")
            # Fallback to agent metadata
            elif "model" not in usage:
                usage["model"] = context.metadata.get("model")

        return usage if usage else None

    def _calculate_cost(self, usage: dict) -> float:
        """Calculate cost in dollars based on token usage.

        Args:
            usage: Dict with input_tokens, output_tokens, model

        Returns:
            Cost in dollars
        """
        model = usage.get("model")
        if not model or model not in self.TOKEN_COSTS:
            return 0.0

        pricing = self.TOKEN_COSTS[model]
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Cost per 1M tokens
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def _log_usage(self, context: MiddlewareContext, usage: dict, cost: float) -> None:
        """Log token usage and cost metrics.

        Args:
            context: Execution context
            usage: Token usage dict
            cost: Calculated cost in dollars
        """
        logger.info(
            f"Token usage for {context.agent_name}: "
            f"{usage.get('total_tokens', 0)} tokens (${cost:.4f})",
            extra={
                "event": "token_usage",
                "execution_id": context.execution_id,
                "agent_name": context.agent_name,
                "session_id": context.session_id,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "model": usage.get("model"),
                "cost_dollars": cost,
                "duration_seconds": context.duration_seconds(),
            },
        )
