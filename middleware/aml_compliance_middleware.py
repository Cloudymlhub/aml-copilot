"""AML compliance middleware for audit trail and regulatory requirements.

Provides audit trail logging for regulatory compliance:
- Immutable execution records
- User attribution
- Decision tracking
- SAR generation audit
- Data access logging

Required for BSA/AML compliance and regulatory examinations.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from middleware.base import BaseMiddleware, MiddlewareContext

logger = logging.getLogger(__name__)


class AMLComplianceMiddleware(BaseMiddleware):
    """Middleware for AML compliance audit trails.

    Creates immutable audit logs for all agent executions to support:
    - Regulatory examinations (OCC, FinCEN, etc.)
    - Internal audit reviews
    - Incident investigation
    - Model risk management documentation
    """

    def __init__(
        self,
        audit_log_dir: Optional[Path] = None,
        log_all_executions: bool = True,
        log_high_risk_only: bool = False,
    ):
        """Initialize AML compliance middleware.

        Args:
            audit_log_dir: Directory to store audit logs (default: ./audit_logs)
            log_all_executions: Log all agent executions
            log_high_risk_only: Only log high-risk operations (SAR, escalations)
        """
        self.audit_log_dir = audit_log_dir or Path("./audit_logs")
        self.audit_log_dir.mkdir(parents=True, exist_ok=True)
        self.log_all_executions = log_all_executions
        self.log_high_risk_only = log_high_risk_only

    async def before_execute(
        self,
        context: MiddlewareContext,
        input_data: Any,
    ) -> None:
        """Record audit trail start."""
        # Initialize audit metadata
        context.metadata["audit"] = {
            "audit_id": context.execution_id,
            "timestamp_start": context.start_time.isoformat(),
            "agent_name": context.agent_name,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "is_high_risk": self._is_high_risk_operation(context, input_data),
        }

    async def after_execute(
        self,
        context: MiddlewareContext,
        output_data: Any,
    ) -> None:
        """Write immutable audit log."""
        audit_data = context.metadata.get("audit", {})
        is_high_risk = audit_data.get("is_high_risk", False)

        # Determine if we should log this execution
        should_log = (
            self.log_all_executions or (self.log_high_risk_only and is_high_risk) or context.error is not None
        )

        if not should_log:
            return

        # Build audit record
        audit_record = {
            "audit_id": audit_data.get("audit_id"),
            "timestamp_start": audit_data.get("timestamp_start"),
            "timestamp_end": context.end_time.isoformat() if context.end_time else None,
            "duration_seconds": context.duration_seconds(),
            "agent_name": context.agent_name,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "execution_status": "failed" if context.error else "success",
            "is_high_risk": is_high_risk,
            "input_summary": self._safe_summary(input_data),
            "output_summary": self._safe_summary(output_data),
            "error_info": self._error_info(context.error) if context.error else None,
            "compliance_flags": self._extract_compliance_flags(output_data),
        }

        # Write to audit log
        self._write_audit_log(audit_record)

        # Log to application logs as well
        logger.info(
            f"Audit trail: {context.agent_name} execution",
            extra={
                "event": "audit_trail",
                **audit_record,
            },
        )

    def _is_high_risk_operation(self, context: MiddlewareContext, input_data: Any) -> bool:
        """Determine if this is a high-risk operation requiring extra scrutiny.

        High-risk operations include:
        - SAR generation/filing
        - Alert dispositions (close/escalate)
        - Customer risk rating changes
        - Suspicious activity determinations

        Args:
            context: Execution context
            input_data: Input to the agent

        Returns:
            True if high-risk operation
        """
        # Check agent name for high-risk agents
        high_risk_agents = {
            "AMLAlertReviewerAgent",
            "SARNarrativeGenerator",
            "DispositionAgent",
        }
        if context.agent_name in high_risk_agents:
            return True

        # Check input for high-risk intents
        if hasattr(input_data, "get") or isinstance(input_data, dict):
            data_dict = dict(input_data) if not isinstance(input_data, dict) else input_data
            intent = data_dict.get("intent", "")
            high_risk_intents = {"file_sar", "escalate_alert", "autonomous_review", "disposition_recommendation"}
            if intent in high_risk_intents:
                return True

        return False

    def _safe_summary(self, data: Any) -> dict:
        """Create a safe summary for audit logs (no PII).

        Args:
            data: Data to summarize

        Returns:
            Dict with summary info safe for audit logs
        """
        if data is None:
            return {"type": "None"}

        summary = {"type": type(data).__name__}

        # For dict-like objects
        if hasattr(data, "get") or isinstance(data, dict):
            data_dict = dict(data) if not isinstance(data, dict) else data

            # Extract non-PII metadata
            summary["keys"] = list(data_dict.keys())
            summary["key_count"] = len(data_dict)

            # Extract specific compliance-relevant fields (no PII)
            safe_fields = {
                "intent",
                "agent_name",
                "disposition",
                "alert_id",
                "alert_type",
                "risk_rating",
                "sar_filed",
                "escalated",
            }
            summary["metadata"] = {k: v for k, v in data_dict.items() if k in safe_fields and not self._is_pii(v)}

        return summary

    def _is_pii(self, value: Any) -> bool:
        """Check if a value might contain PII.

        Conservative check - when in doubt, treat as PII.

        Args:
            value: Value to check

        Returns:
            True if might be PII
        """
        # Complex objects might contain PII
        if isinstance(value, (dict, list)):
            return True

        # Long strings might contain PII
        if isinstance(value, str) and len(value) > 100:
            return True

        return False

    def _error_info(self, error: Exception) -> dict:
        """Extract error information for audit log.

        Args:
            error: Exception that occurred

        Returns:
            Dict with error details
        """
        return {
            "error_type": type(error).__name__,
            "error_message": str(error),
            # Don't include full stack trace in audit log (use app logs for that)
        }

    def _extract_compliance_flags(self, output_data: Any) -> dict:
        """Extract compliance-relevant flags from output.

        Args:
            output_data: Output from agent

        Returns:
            Dict with compliance flags
        """
        flags = {
            "sar_generated": False,
            "alert_escalated": False,
            "alert_closed": False,
            "high_risk_customer": False,
        }

        if output_data is None:
            return flags

        # Extract from dict-like output
        if hasattr(output_data, "get") or isinstance(output_data, dict):
            data_dict = dict(output_data) if not isinstance(output_data, dict) else output_data

            # Check for SAR-related flags
            if "sar_narrative" in data_dict or data_dict.get("disposition") == "FILE_SAR":
                flags["sar_generated"] = True

            # Check for alert disposition
            disposition = data_dict.get("disposition", "")
            if disposition == "ESCALATE":
                flags["alert_escalated"] = True
            elif disposition == "CLOSE":
                flags["alert_closed"] = True

            # Check for high-risk indicators
            if data_dict.get("risk_rating") in ["HIGH", "CRITICAL"]:
                flags["high_risk_customer"] = True

        return flags

    def _write_audit_log(self, audit_record: dict) -> None:
        """Write audit record to immutable log file.

        Uses date-based partitioning for efficient storage and retrieval.

        Args:
            audit_record: Audit record to write
        """
        try:
            # Partition by date for efficient querying
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            log_file = self.audit_log_dir / f"audit_{date_str}.jsonl"

            # Append to JSONL file (one JSON object per line)
            with open(log_file, "a") as f:
                f.write(json.dumps(audit_record) + "\n")

        except Exception as e:
            logger.error(
                f"Failed to write audit log: {e}",
                extra={
                    "event": "audit_log_write_failed",
                    "error": str(e),
                    "audit_id": audit_record.get("audit_id"),
                },
            )
