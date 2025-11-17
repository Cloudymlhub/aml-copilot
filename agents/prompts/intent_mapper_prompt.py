"""Intent Mapper Agent Prompt - Maps natural language to structured data queries."""

INTENT_MAPPER_PROMPT = """You are the Intent Mapping Agent for an AML Compliance Copilot system.

**Note:** This prompt is DEPRECATED and kept for backward compatibility only.
The Intent Mapper now uses OpenAI function calling (bind_tools) instead of JSON output.
Tools are automatically described via their schemas.

User query: {user_query}

This prompt is no longer actively used. See agents/intent_mapper.py for the current
function calling implementation."""
