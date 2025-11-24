"""AML Alert Reviewer Agent - L2 alert review and SAR generation."""

import json
import logging
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AMLCopilotState, AgentResponse
from agents.base_agent import BaseAgent
from agents.prompts.aml_alert_reviewer_prompt import (
    ALERT_REVIEW_PROMPT,
    SAR_NARRATIVE_PROMPT,
    TRANSACTION_PATTERN_ANALYSIS_PROMPT
)
from config.agent_config import AgentConfig
from config.settings import settings


class AMLAlertReviewerAgent(BaseAgent):
    """Specialized agent for operational AML alert review and SAR generation.

    This agent handles:
    - L2 alert disposition analysis (CLOSE/ESCALATE/FILE_SAR)
    - SAR narrative generation
    - Transaction pattern analysis for suspicious activity
    - Red flag assessment and typology matching
    - Regulatory threshold evaluation

    Message History: ALL messages (limit=None)
    Rationale: Alert review requires full investigation context, including
               all previous data retrieval, analysis, and conversation to
               make proper disposition decisions and draft comprehensive SARs.
    """

    def __init__(self, config: AgentConfig):
        """Initialize AML alert reviewer agent.

        Args:
            config: Agent configuration with model settings and history limit
        """
        super().__init__(config)
        self.llm = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_retries=config.max_retries,
            timeout=config.timeout,
            api_key=settings.openai_api_key,
        )

    def __call__(self, state: AMLCopilotState) -> AgentResponse:
        """Execute alert review based on request type.

        Args:
            state: Current state with user query and retrieved data

        Returns:
            AgentResponse with alert review results
        """
        self.log_agent_start(state)

        user_query = state["user_query"]
        intent = state.get("intent", {})
        intent_type = intent.get("intent_type", "") if intent else ""

        # Determine what type of alert review is needed
        query_lower = user_query.lower()

        if "sar" in query_lower and any(word in query_lower for word in ["draft", "write", "generate", "create", "prepare"]):
            return self._generate_sar_narrative(state)
        elif any(word in query_lower for word in ["pattern", "transaction", "structuring", "layering"]):
            return self._analyze_transaction_pattern(state)
        else:
            # Default: alert disposition review
            return self._review_alert(state)

    def _review_alert(self, state: AMLCopilotState) -> AgentResponse:
        """Analyze alert and provide disposition recommendation.

        Args:
            state: Current state

        Returns:
            AgentResponse with disposition decision
        """
        user_query = state["user_query"]
        retrieved_data = state.get("retrieved_data", {})
        history_context = self.get_conversation_history(state, formatted=True)

        # Format retrieved data
        data_str = json.dumps(
            retrieved_data.get("data", {}) if retrieved_data else {},
            indent=2
        )

        def _build_messages(invalid: bool = False):
            prefix = "Your last reply was invalid JSON. Respond with JSON only per schema. " if invalid else ""
            context_section = f"{history_context}\n\n" if history_context else ""

            human_content = (
                f"{prefix}{context_section}"
                f"Alert Review Request: {user_query}\n\n"
                f"Retrieved Data:\n{data_str}"
            )
            return [
                SystemMessage(content=ALERT_REVIEW_PROMPT),
                HumanMessage(content=human_content)
            ]

        def _parse_json(raw_response):
            try:
                return json.loads(raw_response.content)
            except json.JSONDecodeError:
                return None

        # Get alert review
        response = self.llm.invoke(_build_messages())
        result = _parse_json(response)

        # Retry if JSON parsing failed
        if result is None:
            self.logger.warning("AMLAlertReviewer: invalid JSON, retrying once")
            retry_response = self.llm.invoke(_build_messages(invalid=True))
            result = _parse_json(retry_response)

        if result:
            disposition = result.get("disposition", "ESCALATE")
            confidence = result.get("confidence", 0.7)
            risk_level = result.get("risk_level", "MEDIUM")
            red_flags = result.get("red_flags", [])
            typologies = result.get("typologies", [])
            key_findings = result.get("key_findings", [])
            rationale = result.get("rationale", "")
            next_steps = result.get("next_steps", [])
            regulatory_thresholds = result.get("regulatory_thresholds", {})

            # Format final response
            final_response = self._format_alert_disposition(
                disposition=disposition,
                confidence=confidence,
                risk_level=risk_level,
                red_flags=red_flags,
                typologies=typologies,
                key_findings=key_findings,
                rationale=rationale,
                next_steps=next_steps,
                regulatory_thresholds=regulatory_thresholds
            )
        else:
            # Fallback if parsing failed twice
            final_response = (
                "⚠️ Unable to complete alert review. Please provide:\n"
                "- Alert ID and description\n"
                "- Customer information and profile\n"
                "- Transaction details (amounts, dates, counterparties)\n"
                "- Any previous investigation findings"
            )

        return {
            "final_response": final_response,
            "next_agent": "end",
            "current_step": "alert_review_complete",
            "completed": True,
            "messages": self._append_message(state, final_response)
        }

    def _generate_sar_narrative(self, state: AMLCopilotState) -> AgentResponse:
        """Generate SAR narrative based on alert data.

        Args:
            state: Current state

        Returns:
            AgentResponse with SAR narrative
        """
        user_query = state["user_query"]
        retrieved_data = state.get("retrieved_data", {})
        history_context = self.get_conversation_history(state, formatted=True)

        data_str = json.dumps(
            retrieved_data.get("data", {}) if retrieved_data else {},
            indent=2
        )

        context_section = f"{history_context}\n\n" if history_context else ""

        human_content = (
            f"{context_section}"
            f"SAR Generation Request: {user_query}\n\n"
            f"Alert Information:\n{data_str}\n\n"
            f"Generate a comprehensive FinCEN-compliant SAR narrative."
        )

        messages = [
            SystemMessage(content=SAR_NARRATIVE_PROMPT),
            HumanMessage(content=human_content)
        ]

        response = self.llm.invoke(messages)
        sar_narrative = response.content

        # Format with header
        final_response = (
            "# Suspicious Activity Report (SAR) Narrative\n\n"
            f"{sar_narrative}\n\n"
            "---\n"
            "*Note: This narrative should be reviewed by compliance officer before filing.*"
        )

        return {
            "final_response": final_response,
            "next_agent": "end",
            "current_step": "sar_generation_complete",
            "completed": True,
            "messages": self._append_message(state, final_response)
        }

    def _analyze_transaction_pattern(self, state: AMLCopilotState) -> AgentResponse:
        """Analyze transaction patterns for AML red flags.

        Args:
            state: Current state

        Returns:
            AgentResponse with pattern analysis
        """
        user_query = state["user_query"]
        retrieved_data = state.get("retrieved_data", {})
        history_context = self.get_conversation_history(state, formatted=True)

        data_str = json.dumps(
            retrieved_data.get("data", {}) if retrieved_data else {},
            indent=2
        )

        def _build_messages(invalid: bool = False):
            prefix = "Your last reply was invalid JSON. Respond with JSON only per schema. " if invalid else ""
            context_section = f"{history_context}\n\n" if history_context else ""

            human_content = (
                f"{prefix}{context_section}"
                f"Pattern Analysis Request: {user_query}\n\n"
                f"Transaction Data:\n{data_str}"
            )
            return [
                SystemMessage(content=TRANSACTION_PATTERN_ANALYSIS_PROMPT),
                HumanMessage(content=human_content)
            ]

        def _parse_json(raw_response):
            try:
                return json.loads(raw_response.content)
            except json.JSONDecodeError:
                return None

        response = self.llm.invoke(_build_messages())
        result = _parse_json(response)

        if result is None:
            retry_response = self.llm.invoke(_build_messages(invalid=True))
            result = _parse_json(retry_response)

        if result:
            final_response = self._format_pattern_analysis(result)
        else:
            final_response = "Unable to analyze transaction pattern. Please provide transaction data."

        return {
            "final_response": final_response,
            "next_agent": "end",
            "current_step": "pattern_analysis_complete",
            "completed": True,
            "messages": self._append_message(state, final_response)
        }

    def _format_alert_disposition(
        self,
        disposition: str,
        confidence: float,
        risk_level: str,
        red_flags: list,
        typologies: list,
        key_findings: list,
        rationale: str,
        next_steps: list,
        regulatory_thresholds: dict
    ) -> str:
        """Format alert disposition analysis for user presentation."""

        # Disposition emoji
        disposition_emoji = {
            "CLOSE": "✅",
            "ESCALATE": "⚠️",
            "FILE_SAR": "🚨"
        }.get(disposition, "📋")

        # Risk level emoji
        risk_emoji = {
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "CRITICAL": "🔴"
        }.get(risk_level, "⚪")

        response = f"# {disposition_emoji} ALERT DISPOSITION ANALYSIS\n\n"
        response += f"**Recommendation:** {disposition}\n"
        response += f"**Confidence:** {confidence:.0%}\n"
        response += f"**Risk Level:** {risk_emoji} {risk_level}\n\n"

        if key_findings:
            response += "## Key Findings\n"
            for finding in key_findings:
                response += f"- {finding}\n"
            response += "\n"

        if red_flags:
            response += "## Red Flags Identified\n"
            for flag in red_flags:
                response += f"- 🚩 {flag}\n"
            response += "\n"

        if typologies:
            response += "## Matched AML Typologies\n"
            for typology in typologies:
                response += f"- {typology}\n"
            response += "\n"

        if regulatory_thresholds:
            response += "## Regulatory Thresholds\n"
            meets_threshold = regulatory_thresholds.get("meets_sar_threshold", False)
            amount = regulatory_thresholds.get("amount", "N/A")
            basis = regulatory_thresholds.get("threshold_basis", "")
            response += f"- **Meets SAR Threshold:** {'Yes' if meets_threshold else 'No'}\n"
            response += f"- **Amount:** {amount}\n"
            if basis:
                response += f"- **Basis:** {basis}\n"
            response += "\n"

        response += "## Rationale\n"
        response += f"{rationale}\n\n"

        if next_steps:
            response += "## Next Steps\n"
            for step in next_steps:
                response += f"- [ ] {step}\n"

        return response

    def _format_pattern_analysis(self, result: dict) -> str:
        """Format transaction pattern analysis for user presentation."""

        pattern_type = result.get("pattern_type", "UNKNOWN")
        pattern_desc = result.get("pattern_description", "")
        stats = result.get("statistical_analysis", {})
        anomalies = result.get("anomalies", [])
        risk_indicators = result.get("risk_indicators", [])
        comparison = result.get("comparison_to_baseline", "")
        suspicion = result.get("suspicion_level", "NOT_SUSPICIOUS")

        # Suspicion emoji
        suspicion_emoji = {
            "NOT_SUSPICIOUS": "✅",
            "POTENTIALLY_SUSPICIOUS": "⚠️",
            "HIGHLY_SUSPICIOUS": "🚨"
        }.get(suspicion, "📊")

        response = f"# {suspicion_emoji} TRANSACTION PATTERN ANALYSIS\n\n"
        response += f"**Pattern Type:** {pattern_type}\n"
        response += f"**Suspicion Level:** {suspicion}\n\n"

        response += "## Pattern Description\n"
        response += f"{pattern_desc}\n\n"

        if stats:
            response += "## Statistical Analysis\n"
            response += f"- **Total Amount:** {stats.get('total_amount', 'N/A')}\n"
            response += f"- **Transaction Count:** {stats.get('transaction_count', 'N/A')}\n"
            response += f"- **Average Amount:** {stats.get('average_amount', 'N/A')}\n"
            response += f"- **Date Range:** {stats.get('date_range', 'N/A')}\n"
            response += f"- **Frequency:** {stats.get('frequency', 'N/A')}\n\n"

        if anomalies:
            response += "## Anomalies Detected\n"
            for anomaly in anomalies:
                response += f"- ⚠️ {anomaly}\n"
            response += "\n"

        if risk_indicators:
            response += "## AML Risk Indicators\n"
            for indicator in risk_indicators:
                response += f"- 🚩 {indicator}\n"
            response += "\n"

        if comparison:
            response += "## Comparison to Baseline\n"
            response += f"{comparison}\n"

        return response


def create_aml_alert_reviewer_node(config: AgentConfig):
    """Create AML alert reviewer node for LangGraph.

    Args:
        config: Agent configuration

    Returns:
        AML alert reviewer agent callable
    """
    agent = AMLAlertReviewerAgent(config)
    return agent
