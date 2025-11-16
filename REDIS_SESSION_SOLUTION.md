# Redis Session Storage for AML Copilot

## 🎯 User's Requirement

**Store session data in Redis with namespaced keys:**
- `session_id` sent by user in API request
- Namespace: `{user_id}:{session_id}` or `{investigation_id}:{user_id}`
- Use Redis for fast session lookup
- Keep conversation messages in session

---

## ✅ CORRECTED Solution: Redis Session Store

### Why Redis is Better for Your Use Case

**Your Requirements:**
1. ✅ User sends `session_id` in each request
2. ✅ Need fast lookup by session_id
3. ✅ Session data (messages, context) needs to be retrieved quickly
4. ✅ Sessions are short-lived (investigation duration)
5. ✅ Don't need complex queries ("show all sessions for customer X")

**Redis Advantages:**
- ⚡ **Fast** - In-memory, <1ms lookups
- 🔑 **Key-based** - Perfect for session_id lookups
- 🕐 **TTL support** - Auto-expire old sessions
- 📦 **Simple** - No schema, just key-value
- ✅ **Namespacing** - Easy to implement `{user_id}:{session_id}`

**When to use PostgreSQL instead:**
- ❌ Need complex queries (joins, aggregations)
- ❌ Long-term audit trail (years)
- ❌ Regulatory requirement for permanent storage

**Your case: Redis is perfect!**

---

## 🏗️ Implementation

### 1. Redis Session Schema

```python
# Key pattern: session:{user_id}:{session_id}
# Example: session:jane_doe:investigation_abc123

{
    "session_id": "investigation_abc123",
    "user_id": "jane_doe",
    "investigation_id": "INV-2025-001",  # Optional
    "context": {
        "cif_no": "C000001",
        "alert_id": "ALT-456",
    },
    "messages": [
        {
            "role": "user",
            "content": "What's the risk score?",
            "timestamp": "2025-11-16T10:30:00Z"
        },
        {
            "role": "assistant", 
            "content": "Risk score is 75 (HIGH)...",
            "timestamp": "2025-11-16T10:30:05Z",
            "metadata": {
                "compliance_analysis": {...}
            }
        }
    ],
    "created_at": "2025-11-16T10:00:00Z",
    "last_activity": "2025-11-16T10:30:05Z",
    "expires_at": "2025-11-17T10:00:00Z"  # 24h TTL
}
```

### 2. Session Service

```python
# db/services/session_service.py

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import json
from redis import Redis
from config.settings import settings


class SessionService:
    """Redis-based session storage for agent conversations."""
    
    DEFAULT_TTL = 86400  # 24 hours
    MAX_MESSAGES = 50    # Keep last 50 messages per session
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize session service with Redis."""
        if redis_client is None:
            self.redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
        else:
            self.redis = redis_client
    
    def _make_key(self, user_id: str, session_id: str) -> str:
        """Create namespaced session key.
        
        Pattern: session:{user_id}:{session_id}
        """
        return f"session:{user_id}:{session_id}"
    
    def get_session(
        self, 
        user_id: str, 
        session_id: str
    ) -> Optional[Dict]:
        """Get session data from Redis.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Session dict if found, None otherwise
        """
        key = self._make_key(user_id, session_id)
        data = self.redis.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    def create_session(
        self,
        user_id: str,
        session_id: str,
        context: Dict,
        investigation_id: Optional[str] = None,
        ttl: int = DEFAULT_TTL
    ) -> Dict:
        """Create new session in Redis.
        
        Args:
            user_id: User identifier
            session_id: Session identifier  
            context: Session context (cif_no, alert_id, etc.)
            investigation_id: Optional investigation identifier
            ttl: Time to live in seconds
            
        Returns:
            Created session dict
        """
        now = datetime.utcnow().isoformat()
        expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
        
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "investigation_id": investigation_id,
            "context": context,
            "messages": [],
            "created_at": now,
            "last_activity": now,
            "expires_at": expires_at
        }
        
        key = self._make_key(user_id, session_id)
        self.redis.setex(key, ttl, json.dumps(session))
        
        return session
    
    def get_or_create_session(
        self,
        user_id: str,
        session_id: str,
        context: Dict,
        investigation_id: Optional[str] = None
    ) -> Dict:
        """Get existing session or create new one.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            context: Session context
            investigation_id: Optional investigation ID
            
        Returns:
            Session dict
        """
        session = self.get_session(user_id, session_id)
        
        if session:
            # Update last activity
            session["last_activity"] = datetime.utcnow().isoformat()
            # Update context (may have changed)
            session["context"].update(context)
            self._save_session(user_id, session_id, session)
            return session
        
        # Create new session
        return self.create_session(
            user_id, 
            session_id, 
            context,
            investigation_id
        )
    
    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Add message to session conversation.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (compliance_analysis, etc.)
            
        Returns:
            True if successful
        """
        session = self.get_session(user_id, session_id)
        if not session:
            return False
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if metadata:
            message["metadata"] = metadata
        
        # Add message
        session["messages"].append(message)
        
        # Prune old messages if exceeds limit
        if len(session["messages"]) > self.MAX_MESSAGES:
            # Keep most recent messages
            session["messages"] = session["messages"][-self.MAX_MESSAGES:]
        
        # Update last activity
        session["last_activity"] = datetime.utcnow().isoformat()
        
        # Save back to Redis
        return self._save_session(user_id, session_id, session)
    
    def get_messages(
        self,
        user_id: str,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get conversation messages for session.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            limit: Optional limit (returns last N messages)
            
        Returns:
            List of messages
        """
        session = self.get_session(user_id, session_id)
        if not session:
            return []
        
        messages = session.get("messages", [])
        
        if limit and len(messages) > limit:
            return messages[-limit:]
        
        return messages
    
    def update_context(
        self,
        user_id: str,
        session_id: str,
        context: Dict
    ) -> bool:
        """Update session context.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            context: New context values
            
        Returns:
            True if successful
        """
        session = self.get_session(user_id, session_id)
        if not session:
            return False
        
        session["context"].update(context)
        session["last_activity"] = datetime.utcnow().isoformat()
        
        return self._save_session(user_id, session_id, session)
    
    def delete_session(
        self,
        user_id: str,
        session_id: str
    ) -> bool:
        """Delete session from Redis.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            True if deleted
        """
        key = self._make_key(user_id, session_id)
        return self.redis.delete(key) > 0
    
    def extend_ttl(
        self,
        user_id: str,
        session_id: str,
        ttl: int = DEFAULT_TTL
    ) -> bool:
        """Extend session TTL.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            ttl: New TTL in seconds
            
        Returns:
            True if successful
        """
        key = self._make_key(user_id, session_id)
        return self.redis.expire(key, ttl)
    
    def _save_session(
        self,
        user_id: str,
        session_id: str,
        session: Dict,
        ttl: int = DEFAULT_TTL
    ) -> bool:
        """Save session to Redis.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            session: Session data
            ttl: Time to live
            
        Returns:
            True if successful
        """
        key = self._make_key(user_id, session_id)
        try:
            self.redis.setex(key, ttl, json.dumps(session))
            return True
        except Exception as e:
            print(f"Error saving session {key}: {e}")
            return False


# Global session service instance
session_service = SessionService()
```

### 3. Update AMLCopilot to Use Session Service

```python
# agents/graph.py

from db.services.session_service import session_service

class AMLCopilot:
    def __init__(self, agents_config: AgentsConfig):
        """Initialize with configuration."""
        self.config = agents_config
        self.session_service = session_service
        
        # No checkpointer needed - using Redis sessions
        self.graph = create_aml_copilot_graph()
    
    def query(
        self, 
        user_query: str,
        session_id: str,
        user_id: str,
        context: Dict
    ) -> Dict[str, Any]:
        """Process query with Redis session memory.
        
        Args:
            user_query: User's natural language query
            session_id: Session identifier (from API)
            user_id: User identifier (from auth)
            context: Context (cif_no, alert_id, etc.)
            
        Returns:
            Query results with conversation history
        """
        # Get or create session in Redis
        session = self.session_service.get_or_create_session(
            user_id=user_id,
            session_id=session_id,
            context=context
        )
        
        # Get conversation history from Redis
        messages = self.session_service.get_messages(
            user_id=user_id,
            session_id=session_id,
            limit=10  # Last 10 messages for context
        )
        
        # Build state with history
        state: AMLCopilotState = {
            "messages": messages + [
                {
                    "role": "user",
                    "content": user_query,
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "user_query": user_query,
            "context": context,
            "next_agent": "coordinator",
            "current_step": "initialized",
            "session_id": session_id,
            "started_at": datetime.now().isoformat(),
            "completed": False,
            # Other fields...
        }
        
        # Run graph (no checkpointer, just execution)
        final_state = self.graph.invoke(state)
        
        # Save messages back to Redis session
        # User message already added above, save assistant response
        self.session_service.add_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=user_query,
            metadata={"context": context}
        )
        
        self.session_service.add_message(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=final_state.get("final_response", ""),
            metadata={
                "compliance_analysis": final_state.get("compliance_analysis"),
                "retrieved_data": final_state.get("retrieved_data"),
                "intent": final_state.get("intent")
            }
        )
        
        return {
            "response": final_state.get("final_response"),
            "compliance_analysis": final_state.get("compliance_analysis"),
            "retrieved_data": final_state.get("retrieved_data"),
            "session_id": session_id,
            "messages": self.session_service.get_messages(user_id, session_id)
        }
```

### 4. API Integration (Simplified - No JWT Yet)

```python
# api/models.py

class QueryContext(BaseModel):
    """Context for the query."""
    cif_no: str  # Required - customer under investigation
    alert_id: Optional[str] = None
    investigation_id: Optional[str] = None

class QueryRequest(BaseModel):
    """Request model for querying the AML Copilot."""
    query: str = Field(..., description="Natural language query")
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")  # TODO: Move to JWT later
    context: QueryContext = Field(..., description="Query context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the risk score for this customer?",
                "session_id": "investigation_abc123",
                "user_id": "jane_doe",
                "context": {
                    "cif_no": "C000001",
                    "alert_id": "ALT-456"
                }
            }
        }


# api/main.py

@app.post("/api/query")
async def query_copilot(request: QueryRequest):
    """Query with session-based memory.
    
    Note: Currently user_id is in request body for simplicity.
    TODO: Extract user_id from JWT token in future for security.
    """
    
    result = copilot.query(
        user_query=request.query,
        session_id=request.session_id,
        user_id=request.user_id,  # From request body (will be JWT later)
        context=request.context.dict()
    )
    
    return QueryResponse(**result)


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    user_id: str  # TODO: Will come from JWT later
):
    """Get conversation history for session.
    
    Note: user_id as query param for now, will be JWT later.
    """
    messages = session_service.get_messages(user_id, session_id)
    
    return {
        "session_id": session_id,
        "user_id": user_id,
        "message_count": len(messages),
        "messages": messages
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str  # TODO: Will come from JWT later
):
    """End investigation session.
    
    Note: user_id as query param for now, will be JWT later.
    """
    deleted = session_service.delete_session(user_id, session_id)
    
    return {"deleted": deleted}
```

---

## 📊 Comparison: Redis vs PostgreSQL for Sessions

| Aspect | Redis Sessions | PostgreSQL Sessions |
|--------|----------------|---------------------|
| **Speed** | ⚡ <1ms | 🐢 ~50ms |
| **Session lookup** | ✅ O(1) by key | 🟡 Indexed query |
| **TTL support** | ✅ Built-in | ❌ Manual cleanup |
| **Namespacing** | ✅ Easy (`user:session`) | 🟡 Indexed columns |
| **Long-term storage** | ❌ Ephemeral | ✅ Permanent |
| **Complex queries** | ❌ Limited | ✅ Full SQL |
| **Audit trail** | ❌ Expires | ✅ Forever |
| **Your use case** | ✅ **PERFECT** | 🟡 Overkill |

---

## ✅ Final Recommendation

### **Use Redis for Session Storage** ⭐

**Your requirements:**
- ✅ User sends `session_id` in API
- ✅ Fast session lookup by ID
- ✅ Namespaced by `user_id:session_id`
- ✅ Sessions are temporary (investigation duration)
- ✅ Auto-expire with TTL

**Redis is the right choice!**

**Implementation:**
1. ✅ Create `SessionService` (above code)
2. ✅ Store sessions in Redis with namespaced keys
3. ✅ Use TTL for auto-expiration (24h default)
4. ✅ Keep conversation messages in session data
5. ✅ No need for LangGraph checkpointers
6. ✅ No need for PostgreSQL session tables

**Optional: Archive to PostgreSQL**
- If you need long-term audit trail
- Batch write completed sessions to PostgreSQL nightly
- Redis for active sessions, PostgreSQL for history

---

## 🎯 Summary

**You're absolutely right!** 

For your use case (session_id from user, fast lookup, temporary storage):
- ✅ **Redis is better** than PostgreSQL
- ✅ **Simple key-value** is better than complex schemas
- ✅ **Namespacing** (`session:{user_id}:{session_id}`) is perfect
- ✅ **TTL** handles cleanup automatically
- ✅ **No LangGraph checkpointers needed** - just use Redis directly

The code above gives you everything you need!
