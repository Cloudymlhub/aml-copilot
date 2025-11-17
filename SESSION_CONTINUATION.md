# Session Continuation Implementation

## Overview

Session continuation allows the AML Copilot to maintain conversation history across multiple requests within the same session. Users can have multi-turn investigations where the agent remembers previous exchanges.

## What Was Implemented

### 1. **Core Session Continuation in `agents/graph.py`**

**Modified `AMLCopilot.query()` method:**
- Loads previous state from Redis checkpointer before each request
- Appends new message to existing conversation history
- Preserves context (CIF, alert_id) from previous requests if not provided
- Maintains session metadata (started_at, session_id)

**Key Changes:**
```python
# Before (each request started fresh):
initial_state = {
    "messages": [new_user_message],  # Only current message
    ...
}

# After (continues conversation):
if previous_state:
    initial_state = {
        "messages": previous_state["messages"] + [new_user_message],  # Full history!
        "context": context or previous_state.get("context", {}),
        ...
    }
```

### 2. **Helper Methods Added**

**`get_conversation_history(user_id, session_id)`**
- Retrieves all messages from a session
- Returns None if session doesn't exist
- Useful for displaying chat history in UI

**`get_session_info(user_id, session_id)`**
- Returns session metadata:
  - started_at (when conversation began)
  - message_count (number of messages)
  - context (current CIF, alert_id)
  - last_updated (last checkpoint timestamp)

**`clear_session(user_id, session_id)`**
- Deletes session from Redis
- Useful for:
  - Starting fresh investigations
  - Cleaning up test data
  - Privacy/GDPR compliance

### 3. **API Endpoints in `api/main.py`**

**GET `/api/sessions/{user_id}/{session_id}/history`**
- Returns conversation history
- Response includes all messages + message count

**GET `/api/sessions/{user_id}/{session_id}`**
- Returns session metadata
- Useful for session management UI

**DELETE `/api/sessions/{user_id}/{session_id}`**
- Clears a session
- Returns success/not_found status

### 4. **Test Suite in `tests/test_session_continuation.py`**

**Two test scenarios:**

1. **`test_session_continuation()`** - Tests:
   - Multi-turn conversation preserves history
   - Follow-up questions work (reference resolution)
   - Session info retrieval
   - Session clearing

2. **`test_new_vs_existing_session()`** - Tests:
   - New sessions start fresh
   - Existing sessions continue correctly
   - Multiple concurrent sessions don't interfere

## How It Works

### Architecture

```
┌─────────────┐
│   Request   │
│  (user_id,  │
│ session_id) │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────────┐
│  AMLCopilot.query()             │
│  1. Build thread_id             │
│  2. Load previous state (Redis) │  ← NEW!
│  3. Append new message          │  ← NEW!
│  4. Run graph with full history │
│  5. Checkpoint saves to Redis   │
└─────────────────────────────────┘
       │
       ↓
┌─────────────┐
│Redis db=1   │  Stores checkpoints
│(checkpoints)│  Key: {thread_id}:*
└─────────────┘
```

### Redis Storage

**Checkpoint Key Pattern:**
```
thread_id = f"{user_id}_{session_id}"
Keys in Redis db=1:
  - <thread_id>:checkpoint
  - <thread_id>:metadata
  - <thread_id>:writes
```

**Data Stored:**
- Full conversation state (messages, context, etc.)
- Agent workflow state (intents, retrieved_data, etc.)
- Timestamps and metadata

## Example Usage

### Python SDK Example

```python
from agents import AMLCopilot
from config.settings import settings

# Initialize
copilot = AMLCopilot(agents_config=settings.get_agents_config())

user_id = "jane_doe"
session_id = "investigation_abc123"
context = {"cif_no": "C000001", "alert_id": "ALT456"}

# Request 1
result1 = copilot.query(
    user_query="What is the customer's risk score?",
    context=context,
    session_id=session_id,
    user_id=user_id
)
# Response: "Customer C000001 has risk score 27.15 (LOW)"

# Request 2 (continues same session)
result2 = copilot.query(
    user_query="Show me their high-risk transactions",  # "their" = C000001
    context=context,  # Context preserved
    session_id=session_id,  # Same session!
    user_id=user_id
)
# Agent remembers previous conversation!

# Get full history
history = copilot.get_conversation_history(user_id, session_id)
# Returns: [
#   {"role": "user", "content": "What is the customer's risk score?"},
#   {"role": "assistant", "content": "Customer C000001 has risk score..."},
#   {"role": "user", "content": "Show me their high-risk transactions"},
#   {"role": "assistant", "content": "Here are the high-risk transactions..."}
# ]

# Clear session when done
copilot.clear_session(user_id, session_id)
```

### API Example

```bash
# Request 1
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the risk score?",
    "context": {"cif_no": "C000001"},
    "user_id": "jane_doe",
    "session_id": "inv_123"
  }'

# Request 2 (same session - has memory!)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me their transactions",
    "context": {"cif_no": "C000001"},
    "user_id": "jane_doe",
    "session_id": "inv_123"
  }'

# Get conversation history
curl http://localhost:8000/api/sessions/jane_doe/inv_123/history

# Get session info
curl http://localhost:8000/api/sessions/jane_doe/inv_123

# Clear session
curl -X DELETE http://localhost:8000/api/sessions/jane_doe/inv_123
```

## Benefits

### 1. **Natural Multi-Turn Conversations**
```
User: "What's the risk score for C000001?"
Bot: "Risk score is 27.15 (LOW)"

User: "Show me their transactions"  ← Knows "their" = C000001
Bot: "Customer C000001 has 47 transactions..."

User: "Any high-risk ones?"  ← Remembers we're talking about transactions
Bot: "3 transactions flagged as high-risk..."
```

### 2. **Context Preservation**
- CIF number carried forward (don't repeat in every query)
- Alert ID preserved throughout investigation
- Investigation ID maintained

### 3. **Better UX**
- Users don't repeat themselves
- Natural conversation flow
- Can review history

### 4. **Audit Trail**
- Full conversation stored
- Compliance officers can review investigation reasoning
- Timestamps for all interactions

## Implementation Details

### State Merging Logic

**What Gets Preserved:**
- ✅ Messages (conversation history)
- ✅ Context (cif_no, alert_id, investigation_id)
- ✅ Session metadata (started_at, session_id)

**What Gets Cleared Each Request:**
- ❌ Intent (recalculated for new query)
- ❌ Retrieved data (fetched fresh)
- ❌ Compliance analysis (regenerated)
- ❌ Review status (reevaluated)

**Why?** Each query should get fresh analysis, but remember the conversation context.

### Thread ID Format

```python
thread_id = f"{user_id}_{session_id}"
# Example: "jane_doe_investigation_abc123"
```

**Benefits:**
- User-scoped sessions (Jane's session ≠ John's session)
- Multiple sessions per user (investigation A ≠ investigation B)
- Easy to query/clear specific sessions

### Error Handling

**Graceful Degradation:**
```python
try:
    checkpoint = self.graph.get_state(config)
    if checkpoint and checkpoint.values:
        previous_state = checkpoint.values
except Exception:
    # If checkpoint doesn't exist, start fresh
    # No error thrown - just a new conversation
    pass
```

**Checkpointer Optional:**
```python
if self.checkpointer and user_id and session_id:
    # Use checkpointing
else:
    # Fall back to stateless mode (no session continuation)
```

## Testing

**Run tests:**
```bash
# Requires Redis + PostgreSQL + OpenAI API key
PYTHONPATH=/Users/souley/Desktop/code/aml_copilot poetry run python tests/test_session_continuation.py
```

**Test Coverage:**
- ✅ Multi-turn conversations
- ✅ Follow-up questions work
- ✅ Session info retrieval
- ✅ Session clearing
- ✅ Multiple concurrent sessions
- ✅ New vs existing session handling

## Configuration

**Redis Settings:**
```python
# .env or config/settings.py
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB_CHECKPOINTS=1  # Separate from cache (db=0)
```

**No additional configuration needed** - session continuation works automatically when:
1. Redis checkpointer is available (`RedisSaver` initialized)
2. Both `user_id` and `session_id` provided in query

## Limitations & Future Improvements

### Current Limitations

1. **No token limit enforcement** - Long conversations could exceed LLM context window
2. **No automatic summarization** - All messages kept verbatim
3. **No session expiration** - Sessions persist until manually cleared
4. **No session listing** - Can't get all sessions for a user

### Planned Improvements (v2)

1. **Token Management:**
   - Count tokens before sending to LLM
   - Implement sliding window (keep recent + summarize old)
   - Warn users approaching limits

2. **Session Management:**
   - Add session expiration (TTL in Redis)
   - List all sessions for a user
   - Search sessions by date/context

3. **Smart Summarization:**
   - Compress old messages beyond N turns
   - Keep critical information (risk scores, decisions)
   - Reduce token usage for long conversations

4. **Advanced Features:**
   - Session branching (investigate multiple hypotheses)
   - Session merging (combine related investigations)
   - Session templates (common investigation patterns)

## Related Files

**Core Implementation:**
- `agents/graph.py` - AMLCopilot class with session methods
- `agents/state.py` - State schema (messages, context)

**API Layer:**
- `api/main.py` - Session management endpoints

**Configuration:**
- `config/settings.py` - Redis checkpoint config

**Testing:**
- `tests/test_session_continuation.py` - Test suite

**Documentation:**
- `SESSION_CONTINUATION.md` (this file)
- `ARCHITECTURE.md` - Overall system design
- `REDIS_SESSION_SOLUTION.md` - Original design document
