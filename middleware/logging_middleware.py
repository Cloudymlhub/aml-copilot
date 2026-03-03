"""Logging middleware for agent execution tracking.

Provides structured logging for all agent executions with:
- Execution start/end timestamps
- Input/output summaries
- Error logging
- Performance metrics
"""

import logging
from typing import Any

from middleware.base import BaseMiddleware, MiddlewareContext

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware for logging agent execution.

    Logs structured information about agent execution including timing,
    inputs, outputs, and errors.
    """

    def __init__(self, log_level: int = logging.INFO, log_inputs: bool = True, log_outputs: bool = True):
        """Initialize logging middleware.

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_inputs: Whether to log input data summaries
            log_outputs: Whether to log output data summaries
        """
        self.log_level = log_level
        self.log_inputs = log_inputs
        self.log_outputs = log_outputs

    async def before_execute(
        self,
        context: MiddlewareContext,
        input_data: Any,
    ) -> None:
        """Log execution start."""
        log_data = {
            "event": "agent_execution_start",
            "execution_id": context.execution_id,
            "agent_name": context.agent_name,
            "session_id": context.session_id,
            "user_id": context.user_id,
            "timestamp": context.start_time.isoformat(),
        }

        if self.log_inputs:
            log_data["input_summary"] = self._summarize_data(input_data)

        logger.log(self.log_level, f"Starting {context.agent_name}", extra=log_data)

    async def after_execute(
        self,
        context: MiddlewareContext,
        output_data: Any,
    ) -> None:
        """Log execution completion."""
        duration = context.duration_seconds()

        log_data = {
            "event": "agent_execution_complete",
            "execution_id": context.execution_id,
            "agent_name": context.agent_name,
            "session_id": context.session_id,
            "user_id": context.user_id,
            "duration_seconds": duration,
            "timestamp": context.end_time.isoformat() if context.end_time else None,
            "success": context.error is None,
        }

        if self.log_outputs and output_data is not None:
            log_data["output_summary"] = self._summarize_data(output_data)

        if context.error:
            log_data["error_type"] = type(context.error).__name__
            log_data["error_message"] = str(context.error)
            logger.error(f"Failed {context.agent_name} after {duration:.2f}s", extra=log_data)
        else:
            logger.log(
                self.log_level,
                f"Completed {context.agent_name} in {duration:.2f}s",
                extra=log_data,
            )

    async def on_error(
        self,
        context: MiddlewareContext,
        error: Exception,
    ) -> None:
        """Log execution errors with full stack trace."""
        logger.exception(
            f"Error in {context.agent_name}",
            extra={
                "event": "agent_execution_error",
                "execution_id": context.execution_id,
                "agent_name": context.agent_name,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            exc_info=error,
        )

    def _summarize_data(self, data: Any) -> str:
        """Create a safe summary of input/output data.

        Args:
            data: The data to summarize

        Returns:
            A string summary safe for logging (no PII)
        """
        if data is None:
            return "None"

        # For dict-like objects (like State)
        if hasattr(data, "get") or isinstance(data, dict):
            data_dict = dict(data) if not isinstance(data, dict) else data
            # Log keys and types, not values (avoid PII)
            summary = {k: type(v).__name__ for k, v in data_dict.items()}
            return f"Dict[{len(summary)} keys]: {list(summary.keys())}"

        # For list-like objects
        if isinstance(data, (list, tuple)):
            return f"{type(data).__name__}[{len(data)} items]"

        # For simple types
        if isinstance(data, (str, int, float, bool)):
            # Truncate strings to avoid logging sensitive data
            if isinstance(data, str) and len(data) > 100:
                return f"str[{len(data)} chars]: {data[:50]}..."
            return f"{type(data).__name__}: {data}"

        # Fallback
        return f"{type(data).__name__}"
