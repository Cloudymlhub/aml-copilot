# Revised Agent Architecture - Final Design

## 📋 Executive Summary

Based on expert review, the architecture has been simplified with more intuitive patterns:

### Key Improvements
1. **Intuitive Access Control**: `Optional[int]` instead of enum
   - `None` = ALL messages (unlimited access)
   - `0` = NO messages (pure executor)
   - `N` = Last N messages (contextual access)

2. **Type-Safe Returns**: `AgentResponse` TypedDict
   - Clear contract for agent return values
   - IDE auto-completion
   - Compile-time validation

## 🎯 Core Design

### 1. Message History Access (`agents/state.py`)

```python
def get_conversation_context(
    state: AMLCopilotState, 
    message_history_limit: Optional[int]
) -> List[Message]:
    """
    None → ALL messages (comprehensive analysis)
    0 → NO messages (pure executor)
    N → Last N messages (contextual awareness)
    """
```

**Benefits of Optional[int] over Enum:**
- ✅ **More intuitive**: `None` naturally means "unlimited"
- ✅ **More flexible**: Any number of messages, not just 3/10/all
- ✅ **Less boilerplate**: No enum import needed
- ✅ **Standard Python**: Familiar pattern (like `maxlen` in collections)

### 2. Agent Response Type (`agents/state.py`)

```python
class AgentResponse(TypedDict, total=False):
    """Standardized return type for agent __call__ methods.
    
    All fields optional - agents only return what they update.
    """
    # Routing
    next_agent: str
    current_step: str
    
    # Conversation
    messages: List[Message]
    
    # Intent Mapping
    intent: Optional[IntentMapping]
    
    # Data Retrieval
    retrieved_data: Optional[DataRetrievalResult]
    
    # Compliance Analysis
    compliance_analysis: Optional[ComplianceAnalysis]
    
    # Final Response & Review
    final_response: Optional[str]
    review_status: Optional[Literal[...]]
    review_feedback: Optional[str]
    
    # Metadata
    completed: bool
    error: Optional[str]
```

**Benefits:**
- ✅ **Type safety**: Prevents typos in return keys
- ✅ **Documentation**: Clear what agents can return
- ✅ **IDE support**: Auto-completion for return fields
- ✅ **Validation**: Catch errors during development

### 3. BaseAgent Interface (`agents/base_agent.py`)

```python
class BaseAgent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self.message_history_limit = config.message_history_limit
    
    @abstractmethod
    def __call__(self, state: AMLCopilotState) -> AgentResponse:
        """Return AgentResponse dict with state updates."""
        pass
    
    def get_messages(self, state: AMLCopilotState) -> List[Message]:
        """Get messages according to configured limit."""
        return get_conversation_context(state, self.message_history_limit)
```

### 4. Agent Configuration (`config/agent_config.py`)

```python
class AgentConfig(BaseModel):
    model_name: str
    temperature: float = 0.0
    max_retries: int = 3
    timeout: int = 60
    message_history_limit: Optional[int] = 0  # Default: no history
```

### 5. Default Configurations (`config/settings.py`)

```python
coordinator=AgentConfig(
    model_name="gpt-4o-mini",
    message_history_limit=3,  # Last 3 for continuity
)

intent_mapper=AgentConfig(
    model_name="gpt-4o-mini",
    message_history_limit=10,  # Last 10 for references
)

compliance_expert=AgentConfig(
    model_name="gpt-4o",
    message_history_limit=None,  # ALL for analysis
)

review_expert=ReviewAgentConfig(
    model_name="gpt-4o",
    message_history_limit=None,  # ALL for QA
)
```

## 📊 Configuration Matrix

| Agent | Model | History Limit | Rationale |
|-------|-------|---------------|-----------|
| **Coordinator** | gpt-4o-mini | `3` | Basic continuity ("show me more") |
| **Intent Mapper** | gpt-4o-mini | `10` | Reference resolution ("their transactions") |
| **Data Retrieval** | N/A | `0` | Pure executor, no context needed |
| **Compliance Expert** | gpt-4o | `None` | ALL - needs full context for analysis |
| **Review Agent** | gpt-4o | `None` | ALL - comprehensive QA |

## 🔧 Implementation Example

### Before (Ad-hoc pattern)
```python
class MyAgent:
    def __call__(self, state: AMLCopilotState) -> Dict[str, Any]:
        user_query = state["user_query"]
        # No conversation context!
        
        return {
            "next_agent": "end",
            "messages": state["messages"] + [...]  # Manual append
        }
```

### After (BaseAgent interface)
```python
from agents.base_agent import BaseAgent
from agents.state import AgentResponse

class MyAgent(BaseAgent):
    def __call__(self, state: AMLCopilotState) -> AgentResponse:
        self.log_agent_start(state)
        
        # Get conversation context (controlled by config)
        user_query = state["user_query"]
        messages = self.get_messages(state)  # Last N or ALL or NONE
        
        # Use messages for context...
        
        # Return typed response
        return {
            "next_agent": "end",
            "messages": self._append_message(state, "[MyAgent] Done")
        }
```

## 🎓 Design Rationale

### Why Optional[int] > Enum?

**Previous Enum Approach:**
```python
class MessageAccessLevel(Enum):
    NONE = "none"
    RECENT_3 = "recent_3"
    RECENT_10 = "recent_10"
    ALL = "all"
```

**Problems:**
- ❌ Limited to predefined values (what if we need 5 or 7?)
- ❌ Extra imports everywhere
- ❌ More code to maintain
- ❌ Less intuitive (enum values don't map to meaning)

**New Optional[int] Approach:**
```python
message_history_limit: Optional[int]
# None = all, 0 = none, N = last N
```

**Advantages:**
- ✅ Unlimited flexibility (any N)
- ✅ Intuitive meaning (`None` = unlimited)
- ✅ Standard Python pattern
- ✅ Less code, simpler imports
- ✅ Easy to understand: `limit=5` means "last 5 messages"

### Why AgentResponse TypedDict?

**Before:**
```python
def __call__(self, state) -> Dict[str, Any]:  # Too loose!
    return {"next_agnet": "end"}  # Typo! No error until runtime
```

**After:**
```python
def __call__(self, state) -> AgentResponse:  # Type-safe!
    return {"next_agnet": "end"}  # IDE catches typo immediately!
```

## 📝 Migration Pattern

For each agent:

1. **Inherit from BaseAgent**
```python
from agents.base_agent import BaseAgent
from agents.state import AgentResponse

class MyAgent(BaseAgent):
    def __init__(self, config: AgentConfig):
        super().__init__(config)  # Important!
        # ... your init code
```

2. **Update signature**
```python
def __call__(self, state: AMLCopilotState) -> AgentResponse:
    # ↑ Return type is now AgentResponse
```

3. **Use get_messages()**
```python
messages = self.get_messages(state)  # Instead of state["messages"]
```

4. **Use helper methods**
```python
return {
    "messages": self._append_message(state, "[Agent] Done"),
    "next_agent": "end"
}
```

## ✅ Complete Status

### ✅ Infrastructure (Complete)
- [x] `Optional[int]` message access pattern
- [x] `get_conversation_context()` helper
- [x] `AgentResponse` TypedDict
- [x] `BaseAgent` abstract class
- [x] `AgentConfig.message_history_limit` field
- [x] Default configurations
- [x] Exports in `agents/__init__.py`

### 🔄 Next: Agent Refactoring
1. Coordinator (`limit=3`)
2. Intent Mapper (`limit=10`)
3. Compliance Expert (`limit=None`)
4. Review Agent (`limit=None`)
5. Data Retrieval (`limit=0`)

## 🎯 Key Takeaways

1. **Simpler is Better**: `Optional[int]` is more intuitive than enum
2. **Type Safety Matters**: `AgentResponse` catches errors early
3. **Flexibility**: Can use any number of messages (5, 7, 15, etc.)
4. **Standard Patterns**: Uses familiar Python conventions
5. **Easy Configuration**: Just set an integer in config

## 📚 Quick Reference

```python
# Message history configuration
message_history_limit: Optional[int]

# None → ALL messages
config = AgentConfig(message_history_limit=None)

# 0 → NO messages
config = AgentConfig(message_history_limit=0)

# N → Last N messages
config = AgentConfig(message_history_limit=5)  # Last 5
config = AgentConfig(message_history_limit=10)  # Last 10
```

## 🎉 Ready to Implement

The architecture is:
- ✅ **Simpler**: Fewer concepts, more intuitive
- ✅ **Type-safe**: AgentResponse prevents errors
- ✅ **Flexible**: Any number of messages
- ✅ **Standard**: Uses Python conventions
- ✅ **Well-documented**: Clear examples and rationale

**Infrastructure complete. Ready for agent refactoring!**
