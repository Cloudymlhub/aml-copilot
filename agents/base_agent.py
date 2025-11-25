"""Base agent interface for AML Copilot multi-agent system.

This module defines the abstract base class that all agents must implement,
ensuring consistent interfaces and standardized message access patterns.

Design Principles:
- Interface Segregation: Each agent implements a clean, minimal interface
- Template Method Pattern: Base class provides message access, subclasses implement logic
- Configuration-Driven: Access levels declared in config, not hardcoded
- Type Safety: Abstract methods enforce consistent return types
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from agents.state import AMLCopilotState, Message, AgentResponse, get_conversation_context
from config.agent_config import AgentConfig


class BaseAgent(ABC):
    """Abstract base class for all AML Copilot agents.
    
    This class provides a standard interface that all agents must implement:
    1. __call__() - Main entry point for agent execution (returns AgentResponse)
    2. get_messages() - Access to conversation history based on config
    3. Standardized helper methods for common patterns
    
    Benefits:
    - Enforces consistency across all agents
    - Centralizes message access control
    - Makes it easy to add new agents
    - Clear contract for what each agent must do
    - Type-safe return values via AgentResponse
    
    Attributes:
        config: Agent configuration including model settings and history limit
        logger: Logging instance for the agent
        message_history_limit: How many messages this agent can see
            - None: ALL messages (comprehensive analysis)
            - 0: NO messages (pure executor)
            - N: Last N messages (contextual awareness)
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize base agent with configuration.
        
        Args:
            config: Agent configuration with model settings and message_history_limit
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.message_history_limit = config.message_history_limit
        
    @abstractmethod
    def __call__(self, state: AMLCopilotState) -> AgentResponse:
        """Execute agent logic and return state updates.
        
        This is the main entry point called by LangGraph. Each agent must:
        1. Extract needed information from state
        2. Perform its specialized logic
        3. Return an AgentResponse dict (LangGraph merges this into state)
        
        Args:
            state: Current state of the multi-agent system
            
        Returns:
            AgentResponse: Dictionary of state updates to merge into global state.
            Should include 'messages' field to log agent activity.
            
        Example:
            return {
                "next_agent": "data_retrieval",
                "intent": intent_mapping,
                "messages": self._append_message(state, "[MyAgent] Done")
            }
        """
        pass
    
    def get_conversation_history(
        self, 
        state: AMLCopilotState, 
        formatted: bool = False
    ) -> List[Message] | str:
        """Get conversation message history based on this agent's configured limit.
        
        This method provides controlled access to conversation history.
        The amount of history returned is determined by the agent's
        configured message_history_limit:
        
        - None: ALL messages (for comprehensive analysis agents)
        - 0: NO messages (for pure executors that don't need context)
        - N: Last N messages (for contextual awareness)
        
        Args:
            state: Current state containing message history
            formatted: If True, returns formatted string for LLM prompts.
                      If False (default), returns List[Message]
            
        Returns:
            List[Message] if formatted=False, or formatted string if formatted=True
            
        Examples:
            >>> # Get raw message list
            >>> history = self.get_conversation_history(state)
            >>> # Returns: [{"role": "user", "content": "...", ...}, ...]
            
            >>> # Get formatted string for LLM prompt
            >>> context = self.get_conversation_history(state, formatted=True)
            >>> # Returns: "Recent conversation:\nUser: ...\nAssistant: ..."
        """
        messages = get_conversation_context(state, self.message_history_limit)
        
        if not formatted:
            return messages
        
        # Format for LLM prompt
        if not messages:
            return ""
        
        formatted_lines = ["Recent conversation:"]
        for msg in messages:
            role = msg["role"].capitalize()
            content = msg["content"]
            formatted_lines.append(f"{role}: {content}")
        
        return "\n".join(formatted_lines)
    
    def _create_agent_message(self, content: str, state: AMLCopilotState) -> Message:
        """Create a standardized agent message for logging.
        
        Helper method to ensure consistent message formatting across agents.
        
        Args:
            content: Message content (should include agent name prefix)
            state: Current state (for timestamp)
            
        Returns:
            Properly formatted Message dict
            
        Example:
            >>> msg = self._create_agent_message(
            ...     "[Coordinator] Routing to intent_mapper",
            ...     state
            ... )
        """
        return {
            "role": "assistant",
            "content": content,
            "timestamp": str(state.get("started_at", ""))
        }
    
    def _append_message(
        self, 
        state: AMLCopilotState, 
        content: str
    ) -> List[Message]:
        """Append agent message to existing messages.
        
        Convenience method for the common pattern of adding a message.
        
        Args:
            state: Current state with existing messages
            content: New message content
            
        Returns:
            Updated messages list
            
        Example:
            >>> return {
            ...     "messages": self._append_message(state, "[Agent] Done"),
            ...     "next_agent": "end"
            ... }
        """
        new_message = self._create_agent_message(content, state)
        return state["messages"] + [new_message]
    
    def log_agent_start(self, state: AMLCopilotState) -> None:
        """Log agent invocation for debugging.

        Standard logging format for agent startup.

        Args:
            state: Current state
        """
        self.logger.info(
            "%s: invoked for session=%s, history_limit=%s",
            self.__class__.__name__,
            state.get("session_id"),
            self.message_history_limit
        )

    def _parse_json_response(self, response) -> Optional[dict]:
        """Parse JSON from LLM response, returning None on failure.

        Safely attempts to parse JSON from an LLM response object.
        Handles both string content and objects with .content attribute.

        Args:
            response: LLM response object (expects .content attribute)

        Returns:
            Parsed dict if successful, None if parsing fails

        Example:
            >>> response = llm.invoke(messages)
            >>> parsed = self._parse_json_response(response)
            >>> if parsed:
            ...     print(parsed["key"])
            ... else:
            ...     print("Failed to parse JSON")
        """
        try:
            import json
            content = response.content if hasattr(response, 'content') else str(response)
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError, ValueError):
            return None

    def _invoke_with_json_retry(
        self,
        llm,
        messages_builder,
        parse_fallback = None
    ) -> tuple[Optional[dict], any]:
        """Invoke LLM with automatic retry on JSON parse failure.

        This method implements the common pattern of:
        1. Invoke LLM with messages
        2. Try to parse JSON response
        3. If parsing fails, retry once with "invalid JSON" notice
        4. Return parsed result or None

        Args:
            llm: Language model to invoke
            messages_builder: Callable that takes invalid=False/True and returns message list
            parse_fallback: Optional fallback value if parsing fails on both attempts

        Returns:
            Tuple of (parsed_dict, raw_response):
            - parsed_dict: Parsed JSON dict if successful, None otherwise
            - raw_response: The final raw LLM response object

        Example:
            >>> def build_messages(invalid=False):
            ...     prefix = "Invalid JSON. Retry. " if invalid else ""
            ...     return [
            ...         SystemMessage(content=system_prompt),
            ...         HumanMessage(content=f"{prefix}{query}")
            ...     ]
            >>>
            >>> parsed, raw = self._invoke_with_json_retry(
            ...     self.llm,
            ...     build_messages
            ... )
            >>> if parsed:
            ...     result = parsed.get("key")
        """
        # Primary attempt
        response = llm.invoke(messages_builder(invalid=False))
        parsed = self._parse_json_response(response)

        # One-time retry if JSON parsing failed
        if parsed is None:
            self.logger.warning(
                "%s: JSON parse failed, retrying with invalid flag",
                self.__class__.__name__
            )
            response = llm.invoke(messages_builder(invalid=True))
            parsed = self._parse_json_response(response)

            if parsed is None:
                self.logger.error(
                    "%s: JSON parse failed on retry",
                    self.__class__.__name__
                )

        return parsed, response
