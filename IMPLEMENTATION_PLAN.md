# AML Copilot - Implementation Plan

## 🎯 Strategic Design Decisions

### Decision 1: CIF_NO as API State (Not User Input)

#### Current Problem
```python
# Current: User query contains CIF
user_query = "What is the risk score for customer C000001?"
# Intent mapper extracts CIF with regex - fragile!
cif_no = self._extract_cif(query)  # Might fail or be incorrect
```

#### Proposed Solution: CIF as API Parameter
```python
# New API endpoint structure
POST /api/query
{
    "query": "What is the customer's risk score?",
    "context": {
        "cif_no": "C000001",      # Required - known from UI context
        "alert_id": "ALT123",      # Optional - if reviewing an alert
        "session_id": "session_xyz"
    }
}
```

#### Implications

**✅ Benefits:**
- **No ambiguity** - CIF is always known, never guessed
- **Better UX** - User doesn't need to type CIF repeatedly
- **Secure** - API can validate user has access to this CIF
- **Multi-entity** - Can pass multiple CIFs for relationship queries
- **Context-aware** - UI knows which customer is selected

**🔧 Changes Required:**
1. Update `QueryRequest` model to include `context` field
2. Update `AMLCopilotState` to include `context` 
3. Update agents to use `state["context"]["cif_no"]` instead of extracting from query
4. Update prompts to reference context instead of extracting entities
5. Intent mapper focuses on **what to retrieve**, not **who to retrieve for**
6. Update all agent tests

**📋 Example Flow:**
```python
# User viewing customer C000001 in UI asks:
"Show me high-risk transactions from last month"

# API receives:
{
    "query": "Show me high-risk transactions from last month",
    "context": {
        "cif_no": "C000001"
    }
}

# Intent Mapper knows:
- Intent: Get high-risk transactions
- Entity: Already have cif_no from context
- Time range: Last month (extract from query)
- No need to guess CIF!
```

---

### Decision 2: Materialize Feature → Red Flag → Typology Mapping

#### Current State
- `objective.md` mentions typology mapper as Phase 1 component
- Feature catalog has aliases but no typology mappings
- Compliance Expert prompt lists typologies but no systematic mapping

#### Proposed Solution: Typology Mapping Service

**Create `data/typology_mappings.json`:**
```json
{
  "version": "1.0",
  "description": "Feature to Red Flag to Typology mappings for AML compliance",
  "mappings": {
    "structuring": {
      "description": "Breaking up large transactions to avoid reporting thresholds",
      "red_flags": [
        {
          "feature": "count_cash_intensive_txn_w0_90",
          "threshold": ">10",
          "severity": "high",
          "description": "Multiple cash transactions just below reporting threshold"
        },
        {
          "feature": "avg_txn_amount_w0_30",
          "threshold": "9000-9900",
          "severity": "medium",
          "description": "Average transaction amounts consistently near $10k threshold"
        }
      ],
      "regulatory_references": ["FATF Recommendation 10", "BSA Section 5318(g)"]
    },
    "layering": {
      "description": "Complex series of transactions to obscure source of funds",
      "red_flags": [
        {
          "feature": "count_unique_counterparties_w0_90",
          "threshold": ">20",
          "severity": "high",
          "description": "Unusually high number of counterparties"
        },
        {
          "feature": "velocity_score_w0_30",
          "threshold": ">0.8",
          "severity": "medium",
          "description": "Rapid movement of funds"
        }
      ]
    },
    "trade_based_ml": {
      "description": "Using trade transactions to move money",
      "red_flags": [
        {
          "feature": "count_wire_transfers_w0_90",
          "threshold": ">15",
          "severity": "medium",
          "description": "High volume of international wires"
        },
        {
          "feature": "count_high_risk_countries_w0_90",
          "threshold": ">0",
          "severity": "high",
          "description": "Transactions with high-risk jurisdictions"
        }
      ]
    },
    "pep_corruption": {
      "description": "Politically exposed person corruption schemes",
      "red_flags": [
        {
          "feature": "pep_exposure_score",
          "threshold": ">0.5",
          "severity": "critical",
          "description": "Significant PEP connections"
        },
        {
          "feature": "adverse_media_score",
          "threshold": ">0.3",
          "severity": "high",
          "description": "Negative media coverage"
        }
      ]
    }
  }
}
```

**Create `db/services/typology_service.py`:**
```python
class TypologyService:
    """Service for mapping features to typologies."""
    
    def __init__(self, mappings_path: str = "data/typology_mappings.json"):
        self.mappings = self._load_mappings(mappings_path)
    
    def analyze_features(
        self, 
        customer_data: dict
    ) -> List[TypologyMatch]:
        """Analyze customer features and return matched typologies."""
        matches = []
        
        for typology_name, typology_def in self.mappings["mappings"].items():
            for red_flag in typology_def["red_flags"]:
                if self._matches_red_flag(customer_data, red_flag):
                    matches.append(TypologyMatch(
                        typology=typology_name,
                        red_flag=red_flag,
                        confidence=self._calculate_confidence(...)
                    ))
        
        return matches
```

#### Benefits
- **Systematic** - No ad-hoc typology detection
- **Auditable** - Clear mapping from features to conclusions
- **Explainable** - Can show exactly why a typology was flagged
- **Maintainable** - Update mappings without code changes
- **Testable** - Can unit test typology detection logic

#### Integration with Compliance Expert
```python
# Compliance Expert receives:
{
    "customer_data": {...},
    "typology_analysis": {
        "matched_typologies": ["structuring", "layering"],
        "red_flags": [
            {
                "feature": "count_cash_intensive_txn_w0_90",
                "value": 15,
                "threshold": ">10",
                "typology": "structuring"
            }
        ],
        "confidence_scores": {
            "structuring": 0.85,
            "layering": 0.62
        }
    }
}
```

---

### Decision 3: Review Loop for Agent Responses

#### Current State
- Agents produce final responses with no review mechanism
- No human-in-the-loop for critical decisions
- No audit trail of agent reasoning

#### Proposed Solution: Multi-Stage Review System

**Stage 1: Internal Agent Review (Automated)**
```python
# After Compliance Expert generates response
def self_review_response(response: ComplianceAnalysis) -> ReviewResult:
    """Agent reviews its own response for quality/safety."""
    
    # Check for:
    # - Hallucinations (data not in retrieved_data)
    # - Missing critical info
    # - Inappropriate certainty
    # - Regulatory compliance
    
    return ReviewResult(
        approved=True/False,
        confidence=0.85,
        issues=["Missing SAR filing guidance"],
        suggestions=["Add reference to FinCEN requirements"]
    )
```

**Stage 2: Human Review (Optional - Based on Risk)**
```python
class ResponseStatus(str, Enum):
    DRAFT = "draft"                    # Generated, needs review
    PENDING_REVIEW = "pending_review"  # Awaiting human review
    APPROVED = "approved"              # Human approved
    REJECTED = "rejected"              # Human rejected
    AUTO_APPROVED = "auto_approved"    # Low risk, auto-approved

# Store responses for review
class AgentResponse(BaseModel):
    id: str
    session_id: str
    cif_no: str
    query: str
    response: ComplianceAnalysis
    status: ResponseStatus
    risk_level: str  # low, medium, high, critical
    
    # Review fields
    requires_human_review: bool
    reviewed_by: Optional[str]
    review_comments: Optional[str]
    approved_at: Optional[datetime]
    
    # Audit trail
    agent_reasoning: Dict[str, Any]
    retrieved_data: Dict[str, Any]
    typology_matches: List[dict]
```

**Stage 3: Review API Endpoints**
```python
# New endpoints needed
POST /api/query                      # Returns response with status
GET /api/responses/pending           # List responses needing review
POST /api/responses/{id}/approve     # Approve a response
POST /api/responses/{id}/reject      # Reject and provide feedback
GET /api/responses/{id}/audit-trail  # Full reasoning chain
```

#### Review Decision Logic
```python
def should_require_human_review(
    response: ComplianceAnalysis,
    context: dict
) -> bool:
    """Decide if response needs human review."""
    
    # Auto-review (no human needed) if:
    # - Simple data retrieval queries
    # - Low risk customer (risk_score < 30)
    # - No typologies matched
    # - High agent confidence (>0.9)
    
    # Require human review if:
    # - SAR/STR recommendation
    # - High risk typologies (PEP, sanctions)
    # - Risk score > 70
    # - Low agent confidence (<0.6)
    # - Contradictory data
    # - Missing critical information
    
    if response.risk_assessment == "HIGH" or response.risk_assessment == "CRITICAL":
        return True
    
    if "sanctions" in response.typologies or "pep" in response.typologies:
        return True
    
    if any(rec.startswith("File SAR") for rec in response.recommendations):
        return True
    
    return False
```

#### Review Loop Integration
```python
# Updated graph with review node
def create_aml_copilot_graph(agents_config: AgentsConfig):
    workflow = StateGraph(AMLCopilotState)
    
    # Existing nodes
    workflow.add_node("coordinator", ...)
    workflow.add_node("intent_mapper", ...)
    workflow.add_node("data_retrieval", ...)
    workflow.add_node("compliance_expert", ...)
    
    # NEW: Review nodes
    workflow.add_node("self_review", create_self_review_node())
    workflow.add_node("store_for_review", create_store_node())
    
    # Updated routing
    workflow.add_conditional_edges(
        "compliance_expert",
        route_to_review,
        {
            "self_review": "self_review",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "self_review",
        route_after_self_review,
        {
            "store_for_review": "store_for_review",  # Needs human review
            END: END  # Auto-approved
        }
    )
```

---

## 🧠 Memory & Conversation Analysis

### Current State: NO PERSISTENT MEMORY

**What Currently Happens:**
```python
# Each query starts fresh
def query(self, user_query: str, session_id: str = None):
    initial_state = {
        "messages": [{"role": "user", "content": user_query}],  # Only current query!
        # ... rest of state
    }
    final_state = self.graph.invoke(initial_state)
    return final_state  # State is LOST after response
```

**Issues:**
1. ❌ **No conversation continuity** - Each query is isolated
2. ❌ **Can't reference previous queries** - "Show me more details" doesn't work
3. ❌ **No session persistence** - session_id is tracked but not stored
4. ❌ **Agents don't have conversation context** - Can't build on previous answers
5. ❌ **Messages list is internal only** - Not persisted anywhere

**Example of Problem:**
```
User: "What's the risk score for customer C000001?"
Agent: "Risk score is 75 (HIGH)"

User: "Show me their transactions"  # <-- This fails!
Agent: "Which customer?" # Agent forgot context!
```

---

### Memory Strategy Options

#### **Option 1: Stateless (Current) - Simple but Limited**
```python
# Each query independent
query(user_query="Show me risk score", session_id="xyz")
# No memory between queries
```

**Pros:**
- ✅ Simple to implement (already done)
- ✅ No storage needed
- ✅ No memory leaks
- ✅ Easy to scale (stateless)

**Cons:**
- ❌ Poor UX (can't reference previous queries)
- ❌ Users repeat context every time
- ❌ Can't build on previous analysis

**Use Case:** Simple one-shot queries, no conversation needed

---

#### **Option 2: In-Memory Session State - Fast but Ephemeral**
```python
# Store session state in memory (dict or Redis)
session_store = {}  # or Redis

def query(user_query, session_id):
    # Load previous state
    previous_state = session_store.get(session_id, default_state)
    
    # Add new message to history
    previous_state["messages"].append({"role": "user", "content": user_query})
    
    # Run graph with history
    new_state = self.graph.invoke(previous_state)
    
    # Save back to memory
    session_store[session_id] = new_state
    return new_state
```

**Pros:**
- ✅ Fast (in-memory)
- ✅ Conversation continuity within session
- ✅ Can reference previous queries
- ✅ Simple to implement

**Cons:**
- ❌ Lost on server restart
- ❌ Memory grows unbounded (need eviction)
- ❌ Can't audit past conversations
- ❌ Single-server only (doesn't scale horizontally)

**Use Case:** Development, demos, short sessions

---

#### **Option 3: Database-Backed Sessions - Persistent & Auditable**
```python
# Store in PostgreSQL
class SessionRepository:
    def get_session(self, session_id: str) -> Optional[Session]:
        """Load session and conversation history."""
        
    def save_message(self, session_id: str, message: Message):
        """Append message to conversation history."""
        
    def get_recent_messages(self, session_id: str, limit: int = 10):
        """Get last N messages for context."""

def query(user_query, session_id):
    # Load recent conversation history from DB
    history = session_repo.get_recent_messages(session_id, limit=10)
    
    # Build state with history
    state = {
        "messages": history + [{"role": "user", "content": user_query}],
        "session_id": session_id,
        # ...
    }
    
    # Run graph
    final_state = self.graph.invoke(state)
    
    # Persist new messages to DB
    for msg in final_state["messages"]:
        session_repo.save_message(session_id, msg)
    
    return final_state
```

**Pros:**
- ✅ Survives restarts
- ✅ Full audit trail
- ✅ Can query conversation history
- ✅ Scales horizontally
- ✅ Can implement analytics

**Cons:**
- ❌ Slower than in-memory (DB round-trips)
- ❌ More complex to implement
- ❌ Need DB schema and migrations

**Use Case:** Production, compliance, audit requirements

---

#### **Option 4: Hybrid (Redis + PostgreSQL) - Best of Both**
```python
# Redis for hot session data, PostgreSQL for persistence
class HybridSessionService:
    def __init__(self, redis_client, db_repo):
        self.redis = redis_client
        self.db = db_repo
    
    def get_session_context(self, session_id: str):
        # Try Redis first (fast)
        cached = self.redis.get(f"session:{session_id}")
        if cached:
            return json.loads(cached)
        
        # Fall back to DB
        history = self.db.get_recent_messages(session_id, limit=10)
        
        # Cache in Redis
        self.redis.setex(f"session:{session_id}", 3600, json.dumps(history))
        return history
    
    def save_message(self, session_id, message):
        # Write to both
        self.redis.lpush(f"session:{session_id}:messages", json.dumps(message))
        self.db.save_message(session_id, message)
```

**Pros:**
- ✅ Fast (Redis cache)
- ✅ Persistent (PostgreSQL backup)
- ✅ Scalable
- ✅ Audit trail

**Cons:**
- ❌ Most complex
- ❌ Need to manage cache invalidation
- ❌ Two systems to maintain

**Use Case:** High-scale production

---

### Memory Implementation Patterns

#### **Pattern 1: Full Context (Simple)**
```python
# Load ALL messages from session
messages = db.get_all_messages(session_id)  # Could be 100+ messages
state = {"messages": messages, ...}
# Problem: Token limit exceeded for long conversations!
```

#### **Pattern 2: Sliding Window (Practical)**
```python
# Only load recent messages
messages = db.get_recent_messages(session_id, limit=10)  # Last 10 messages
state = {"messages": messages, ...}
# Works well for most cases
```

#### **Pattern 3: Summarization (Advanced)**
```python
# Summarize old messages, keep recent ones
old_summary = db.get_conversation_summary(session_id)  # LLM-generated summary
recent_messages = db.get_recent_messages(session_id, limit=5)

state = {
    "conversation_summary": old_summary,  # "User asked about customer C000001..."
    "messages": recent_messages,  # Last 5 messages
    ...
}
# Best: Maintains context without token explosion
```

---

### ⭐ FINAL DECISION: Redis Session Storage

**User's requirement clarified:**
- ✅ User sends `session_id` in API request
- ✅ Need fast session lookup by ID
- ✅ Sessions are investigation-scoped (temporary, hours/days)
- ✅ Want to leverage Redis with namespacing

**Redis is the right choice!**

**Why Redis > PostgreSQL for sessions:**
- ⚡ **Speed**: <1ms lookups vs ~50ms
- 🔑 **Key-based access**: Perfect for session_id lookups
- 🕐 **TTL support**: Auto-expire old sessions (24h)
- 📦 **Simple**: No schema, just key-value
- 🎯 **Namespacing**: Easy `session:{user_id}:{session_id}` pattern

**Why NOT use LangGraph checkpointers:**
- ❌ Designed for graph execution state (debug/resume)
- ❌ Not optimized for simple session lookups
- ❌ Overkill for your use case
- ✅ Redis is simpler and faster

**Implementation:**
```python
# Redis key pattern
session:{user_id}:{session_id} → {
    "session_id": "...",
    "user_id": "...",
    "context": {"cif_no": "C000001", ...},
    "messages": [...],
    "created_at": "...",
    "expires_in": 86400  # 24h
}
```

**See `REDIS_SESSION_SOLUTION.md` for complete implementation**

**Implementation:**
```python
# db/models/session.py
class Session(BaseModel):
    id: int
    session_id: str
    user_id: str
    cif_no: Optional[str]  # Current customer context
    created_at: datetime
    last_activity: datetime
    expires_at: datetime

class ConversationMessage(BaseModel):
    id: int
    session_id: str
    role: str  # user, assistant, system
    content: str
    metadata: dict  # intent, retrieved_data, etc.
    created_at: datetime

# db/repositories/session_repository.py
class SessionRepository:
    def create_or_get_session(self, session_id: str, user_id: str):
        """Get existing session or create new one."""
        
    def get_recent_messages(self, session_id: str, limit: int = 10):
        """Get last N messages for context window."""
        
    def save_message(self, session_id: str, message: Message):
        """Persist message to conversation history."""
        
    def expire_old_sessions(self, max_age_days: int = 30):
        """Clean up old sessions."""

# agents/graph.py
class AMLCopilot:
    def __init__(self, session_repo: SessionRepository):
        self.session_repo = session_repo
        self.graph = create_aml_copilot_graph()
    
    def query(self, user_query: str, session_id: str, user_id: str):
        # Get or create session
        session = self.session_repo.create_or_get_session(session_id, user_id)
        
        # Load recent conversation history
        history = self.session_repo.get_recent_messages(session_id, limit=10)
        
        # Build state with history
        state = {
            "messages": history + [{"role": "user", "content": user_query}],
            "session_id": session_id,
            "context": {"cif_no": session.cif_no} if session.cif_no else {},
            # ... rest
        }
        
        # Run graph
        final_state = self.graph.invoke(state)
        
        # Persist new messages
        for msg in final_state["messages"]:
            if msg not in history:  # Only save new messages
                self.session_repo.save_message(session_id, msg)
        
        return final_state
```

---

### Token Management Strategy

**Problem:** Long conversations exceed LLM context limits

**Solution: Adaptive Context Window**
```python
def get_context_for_session(session_id: str, max_tokens: int = 4000):
    """Smart context loading with token management."""
    
    messages = []
    token_count = 0
    
    # Always include system prompt
    system_prompt = get_system_prompt()
    token_count += count_tokens(system_prompt)
    
    # Load messages newest-first until token limit
    recent_messages = db.get_messages_desc(session_id)
    for msg in recent_messages:
        msg_tokens = count_tokens(msg.content)
        if token_count + msg_tokens > max_tokens:
            break
        messages.insert(0, msg)  # Maintain chronological order
        token_count += msg_tokens
    
    # If we hit limit and have old messages, add summary
    if len(recent_messages) > len(messages):
        summary = db.get_or_create_summary(session_id, exclude=messages)
        messages.insert(0, {"role": "system", "content": f"Previous context: {summary}"})
    
    return messages
```

---

## 📋 Complete Implementation Checklist

### Phase 1: Core Infrastructure (DI & Configuration)

- [ ] **1.1 Agent Configuration**
  - [ ] Create `config/agent_config.py` with `AgentConfig` and `AgentsConfig`
  - [ ] Update `config/settings.py` with per-agent model settings
  - [ ] Create `.env.example` with all configuration options
  - [ ] Add configuration validation

- [ ] **1.2 Dependency Injection**
  - [ ] Update `CoordinatorAgent.__init__()` to accept config
  - [ ] Update `IntentMappingAgent.__init__()` to accept config
  - [ ] Update `DataRetrievalAgent.__init__()` to accept config
  - [ ] Update `ComplianceExpertAgent.__init__()` to accept config
  - [ ] Update all `create_*_node()` functions to accept config
  - [ ] Update `create_aml_copilot_graph()` to accept config
  - [ ] Update `AMLCopilot.__init__()` to accept config

- [ ] **1.3 API Integration**
  - [ ] Update API lifespan to read settings and create configs
  - [ ] Add logging for which models are being used
  - [ ] Add endpoint to get current configuration

### Phase 2: Context-Aware Queries (CIF as API State)

- [ ] **2.1 Data Models**
  - [ ] Add `QueryContext` model with `cif_no`, `alert_id`, etc.
  - [ ] Update `QueryRequest` to include `context: QueryContext`
  - [ ] Update `AMLCopilotState` to include `context`
  - [ ] Add validation for required context fields

- [ ] **2.2 Agent Updates**
  - [ ] Update coordinator to pass context through state
  - [ ] Update intent mapper to use `state["context"]["cif_no"]` instead of extraction
  - [ ] Simplify `_extract_cif()` to be optional/validation only
  - [ ] Update prompts to reference context
  - [ ] Update data retrieval agent to use context

- [ ] **2.3 API Updates**
  - [ ] Update `/api/query` endpoint to require context
  - [ ] Add request validation for context
  - [ ] Update API documentation with examples

- [ ] **2.4 Tests**
  - [ ] Update all agent tests to include context
  - [ ] Add tests for missing/invalid context
  - [ ] Add integration tests with context

### Phase 3: Typology Mapping System

- [ ] **3.1 Typology Mappings**
  - [ ] Create `data/typology_mappings.json` with comprehensive mappings
  - [ ] Document each typology with red flags and thresholds
  - [ ] Add regulatory references
  - [ ] Add severity levels

- [ ] **3.2 Typology Service**
  - [ ] Create `db/services/typology_service.py`
  - [ ] Implement `TypologyService` class
  - [ ] Implement `analyze_features()` method
  - [ ] Implement red flag matching logic
  - [ ] Implement confidence scoring
  - [ ] Add caching for typology analysis

- [ ] **3.3 Data Models**
  - [ ] Create `TypologyMatch` model
  - [ ] Create `RedFlagMatch` model
  - [ ] Add to state for passing between agents

- [ ] **3.4 Integration**
  - [ ] Update data retrieval agent to call typology service
  - [ ] Pass typology analysis to compliance expert
  - [ ] Update compliance expert prompt to use typology analysis
  - [ ] Update response models to include typology details

- [ ] **3.5 Tests**
  - [ ] Unit tests for typology matching
  - [ ] Integration tests with real customer data
  - [ ] Edge case tests (no matches, multiple matches)

### Phase 4: Review Loop System

- [ ] **4.1 Review Models**
  - [ ] Create `ResponseStatus` enum
  - [ ] Create `AgentResponse` model with review fields
  - [ ] Create `ReviewResult` model
  - [ ] Create `AuditTrail` model

- [ ] **4.2 Storage Layer**
  - [ ] Create `agent_responses` database table
  - [ ] Create `ResponseRepository` for CRUD operations
  - [ ] Add migration for new tables
  - [ ] Create indexes for queries

- [ ] **4.3 Review Logic**
  - [ ] Implement `self_review_response()` function
  - [ ] Implement `should_require_human_review()` logic
  - [ ] Create self-review agent/node
  - [ ] Create store-for-review node

- [ ] **4.4 Graph Updates**
  - [ ] Add review nodes to graph
  - [ ] Add routing logic for review flow
  - [ ] Update state to track review status
  - [ ] Add review result to response

- [ ] **4.5 Review API Endpoints**
  - [ ] `GET /api/responses/pending` - List pending reviews
  - [ ] `GET /api/responses/{id}` - Get response details
  - [ ] `POST /api/responses/{id}/approve` - Approve response
  - [ ] `POST /api/responses/{id}/reject` - Reject with feedback
  - [ ] `GET /api/responses/{id}/audit-trail` - Full reasoning
  - [ ] `GET /api/responses/stats` - Review statistics

- [ ] **4.6 UI Integration Points**
  - [ ] Response shows status badge (pending, approved, etc.)
  - [ ] Reviewer dashboard for pending items
  - [ ] Audit trail viewer
  - [ ] Feedback mechanism

- [ ] **4.7 Tests**
  - [ ] Unit tests for review logic
  - [ ] Integration tests for review flow
  - [ ] Test different risk scenarios
  - [ ] Test approval/rejection flow

### Phase 5: Session Management (Redis-based) ⭐ FINAL DECISION

- [ ] **5.1 Redis Session Service** 
  - [ ] Create `db/services/session_service.py`
  - [ ] Implement `SessionService` class with namespaced keys (`session:{user_id}:{session_id}`)
  - [ ] Methods: `get_session()`, `create_session()`, `add_message()`, `get_messages()`
  - [ ] Use TTL for auto-expiration (24h default)
  - [ ] Store: session_id, user_id, context, messages, timestamps

- [ ] **5.2 Update AMLCopilot for Redis Sessions**
  - [ ] Inject `SessionService` into `AMLCopilot.__init__()`
  - [ ] Load conversation history from Redis before graph execution
  - [ ] Save messages back to Redis after execution
  - [ ] Remove LangGraph checkpointer (not needed)

- [ ] **5.3 Update API Models**
  - [ ] Add `QueryContext` model (cif_no, alert_id, investigation_id)
  - [ ] Update `QueryRequest` to require `session_id` and `context`
  - [ ] Extract `user_id` from authentication

- [ ] **5.4 Session API Endpoints**
  - [ ] Update `POST /api/query` to use session service
  - [ ] Add `GET /api/sessions/{session_id}/history`
  - [ ] Add `DELETE /api/sessions/{session_id}` (end session)
  - [ ] Add `PUT /api/sessions/{session_id}/context` (update context)

- [ ] **5.5 Optional: Archive to PostgreSQL** (if audit trail needed)
  - [ ] Create batch job to archive completed sessions
  - [ ] Keep active sessions in Redis, history in PostgreSQL

- [ ] **5.4 Context Carryover**
  - [ ] Load previous messages when session_id provided
  - [ ] Implement context window management
  - [ ] Add conversation state persistence
  - [ ] Enable "remember previous query" functionality

- [ ] **5.5 Multi-Entity Queries**
  - [ ] Support multiple CIFs in context
  - [ ] Relationship queries between entities
  - [ ] Network analysis across customers

- [ ] **5.3 Async Processing**
  - [ ] Make all agents fully async
  - [ ] Add background task queue for long-running queries
  - [ ] Add WebSocket support for real-time updates

- [ ] **5.4 Monitoring & Observability**
  - [ ] Add structured logging
  - [ ] Add metrics (query time, token usage, etc.)
  - [ ] Add tracing for agent decisions
  - [ ] Add alerting for failures

### Phase 6: Testing & Documentation

- [ ] **6.1 Comprehensive Tests**
  - [ ] Unit tests for all services
  - [ ] Integration tests for full flow
  - [ ] End-to-end tests with real scenarios
  - [ ] Performance tests

- [ ] **6.2 Documentation**
  - [ ] API documentation (OpenAPI/Swagger)
  - [ ] Agent architecture documentation
  - [ ] Configuration guide
  - [ ] Deployment guide
  - [ ] Troubleshooting guide

---

## 🔄 Updated Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. API Request                                              │
│    POST /api/query                                          │
│    {                                                        │
│      query: "Show high-risk transactions",                 │
│      context: { cif_no: "C000001", session_id: "..." }     │
│    }                                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Initialize State (with Context)                         │
│    state = {                                                │
│      user_query: "...",                                     │
│      context: { cif_no: "C000001", ... },                  │
│      ...                                                    │
│    }                                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Coordinator (with DI Config)                            │
│    - Uses configured model (gpt-4, gpt-4o-mini, etc.)      │
│    - Routes based on query type                            │
│    - Passes context through                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Intent Mapper (Simplified)                              │
│    - Uses state["context"]["cif_no"] (no extraction!)      │
│    - Focuses on WHAT to retrieve                           │
│    - Maps to feature groups & tools                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Data Retrieval                                          │
│    - Executes tools with context CIF                       │
│    - Returns customer data                                 │
│    ┌─────────────────────────────────────────────┐         │
│    │ 5a. Typology Service                        │         │
│    │   - Analyzes features                       │         │
│    │   - Matches red flags                       │         │
│    │   - Returns typology matches                │         │
│    └─────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Compliance Expert                                       │
│    - Receives data + typology analysis                     │
│    - Generates compliance analysis                         │
│    - Provides recommendations                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Self-Review Node (NEW)                                  │
│    - Checks for hallucinations                             │
│    - Validates against retrieved data                      │
│    - Checks completeness                                   │
│    - Calculates confidence                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────┴───────┐
                    │               │
                Auto-Approve    Needs Review
                    │               │
                    ↓               ↓
            ┌──────────────┐  ┌──────────────┐
            │ Return Now   │  │ Store & Queue│
            │ (Low Risk)   │  │ (High Risk)  │
            └──────────────┘  └──────────────┘
                    │               │
                    ↓               ↓
            ┌──────────────┐  ┌──────────────┐
            │ Response     │  │ Pending      │
            │ status:      │  │ status:      │
            │ auto_approved│  │ pending_review│
            └──────────────┘  └──────────────┘
```

---

## 🚀 Suggested Implementation Order

### Sprint 1 (Week 1): Foundation
1. DI & Configuration (Phase 1) - **Critical blocker**
2. Basic tests to verify DI works

### Sprint 2 (Week 2): Context-Aware System
1. Context API changes (Phase 2)
2. Update all agents for context
3. Update tests

### Sprint 3 (Week 3): Intelligence Layer
1. Typology mappings (Phase 3)
2. Typology service
3. Integration with agents

### Sprint 4 (Week 4): Review System
1. Review models & storage (Phase 4.1-4.2)
2. Review logic (Phase 4.3)
3. Graph updates (Phase 4.4)

### Sprint 5 (Week 5): Review UI & Polish
1. Review API endpoints (Phase 4.5)
2. UI integration (Phase 4.6)
3. Comprehensive testing

### Sprint 6+ (Ongoing): Enhanced Features
1. Session management
2. Multi-entity queries
3. Async processing
4. Monitoring

---

## ⚠️ Critical Dependencies

1. **Phase 1 must be done first** - Everything depends on DI
2. **Phase 2 should be done early** - Simplifies all downstream work
3. **Phase 3 can be parallel** with Phase 2 after Phase 1
4. **Phase 4 depends on** Phases 1-3 being complete

---

## 🎯 Success Metrics

**Configuration Flexibility:**
- ✅ Can change models via .env without code changes
- ✅ Can run different configs in dev/staging/prod

**Context Clarity:**
- ✅ Zero CIF extraction errors
- ✅ 100% context propagation through agents

**Typology Accuracy:**
- ✅ >90% precision on known typologies
- ✅ Clear audit trail from feature → red flag → typology

**Review Efficiency:**
- ✅ <10% of queries require human review
- ✅ <5 minutes average review time
- ✅ Zero approved hallucinations

---

## 📝 Notes

- Keep `API_REVIEW.md` for DI-specific details
- This document is the master plan
- Update checklist as work progresses
- Add new sections as requirements emerge
