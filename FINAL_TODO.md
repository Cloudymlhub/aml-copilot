# AML Copilot - Final Implementation Todo List

## 📋 Overview

This is the consolidated, agreed-upon implementation plan. All previous markdown documents (IMPLEMENTATION_PLAN.md, API_REVIEW.md, REDIS_SESSION_SOLUTION.md, LANGGRAPH_MEMORY_ANALYSIS.md) have been reviewed and distilled into this actionable list.

**Key Architecture Decisions:**
1. ✅ **CIF as API context** - Not extracted from user query
2. ✅ **Materialize typology mappings** - Systematic red flag detection
3. ✅ **Review loop** - Self-review + optional human review
4. ✅ **Redis for sessions** - LangGraph RedisSaver for chat continuity
5. ✅ **Simple MVP auth** - user_id/session_id in request body (JWT later)

---

## 🚀 Phase 1: Dependency Injection & Configuration (CRITICAL - DO THIS FIRST)

### 1.1 Create Agent Configuration Models
**File:** `config/agent_config.py` (new file)

```python
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    """Configuration for a single agent."""
    model_name: str = Field(..., description="LLM model name (e.g., gpt-4o-mini)")
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    max_retries: int = Field(3, ge=1)
    timeout: int = Field(60, ge=10)  # seconds

class AgentsConfig(BaseModel):
    """Configuration for all agents."""
    coordinator: AgentConfig
    intent_mapper: AgentConfig
    data_retrieval: AgentConfig
    compliance_expert: AgentConfig
```

**Why:** Agents currently hardcode "gpt-4o-mini". This creates proper config structure.

---

### 1.2 Update Settings with Per-Agent Configs
**File:** `config/settings.py`

**Add these fields:**
```python
# Per-agent LLM configurations
coordinator_model: str = "gpt-4o-mini"
coordinator_temperature: float = 0.0
intent_mapper_model: str = "gpt-4o-mini"
intent_mapper_temperature: float = 0.0
data_retrieval_model: str = "gpt-4o-mini"
data_retrieval_temperature: float = 0.0
compliance_expert_model: str = "gpt-4o"  # More powerful for compliance
compliance_expert_temperature: float = 0.1

# Redis configuration for RedisSaver
redis_db_checkpoints: int = 1  # For LangGraph state
redis_db_cache: int = 0  # For data caching
```

**Add method:**
```python
def get_agents_config(self) -> AgentsConfig:
    """Build agents configuration from settings."""
    return AgentsConfig(
        coordinator=AgentConfig(
            model_name=self.coordinator_model,
            temperature=self.coordinator_temperature,
        ),
        intent_mapper=AgentConfig(
            model_name=self.intent_mapper_model,
            temperature=self.intent_mapper_temperature,
        ),
        data_retrieval=AgentConfig(
            model_name=self.data_retrieval_model,
            temperature=self.data_retrieval_temperature,
        ),
        compliance_expert=AgentConfig(
            model_name=self.compliance_expert_model,
            temperature=self.compliance_expert_temperature,
        ),
    )
```

---

### 1.3 Update All Agent Constructors
**Files:** `agents/coordinator.py`, `agents/intent_mapper.py`, `agents/data_retrieval.py`, `agents/compliance_expert.py`

**Change from:**
```python
class CoordinatorAgent:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
```

**To:**
```python
from config.agent_config import AgentConfig

class CoordinatorAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_retries=config.max_retries,
            timeout=config.timeout,
        )
```

**Repeat for all 4 agents.**

---

### 1.4 Update Graph Creation Functions
**File:** `agents/graph.py`

**Update node creation functions:**
```python
from config.agent_config import AgentsConfig

def create_coordinator_node(config: AgentConfig):
    """Create coordinator node with config."""
    agent = CoordinatorAgent(config)
    return agent.process

def create_intent_mapper_node(config: AgentConfig):
    """Create intent mapper node with config."""
    agent = IntentMappingAgent(config)
    return agent.process

# ... similar for data_retrieval and compliance_expert
```

**Update graph creation:**
```python
def create_aml_copilot_graph(agents_config: AgentsConfig, checkpointer=None):
    """Create graph with agent configs and optional checkpointer."""
    workflow = StateGraph(AMLCopilotState)
    
    # Add nodes with configs
    workflow.add_node("coordinator", create_coordinator_node(agents_config.coordinator))
    workflow.add_node("intent_mapper", create_intent_mapper_node(agents_config.intent_mapper))
    workflow.add_node("data_retrieval", create_data_retrieval_node(agents_config.data_retrieval))
    workflow.add_node("compliance_expert", create_compliance_expert_node(agents_config.compliance_expert))
    
    # ... rest of workflow setup ...
    
    return workflow.compile(checkpointer=checkpointer)
```

---

### 1.5 Update AMLCopilot Class
**File:** `agents/graph.py`

**Update constructor:**
```python
from langgraph.checkpoint.redis import RedisSaver
from config.settings import settings
from config.agent_config import AgentsConfig

class AMLCopilot:
    def __init__(self, agents_config: AgentsConfig):
        """Initialize with agent configs and Redis checkpointer."""
        self.config = agents_config
        
        # Create RedisSaver for chat continuity
        self.checkpointer = RedisSaver.from_conn_info(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db_checkpoints,
        )
        
        # Create graph with configs and checkpointer
        self.graph = create_aml_copilot_graph(
            agents_config=agents_config,
            checkpointer=self.checkpointer
        )
```

---

### 1.6 Update API Initialization
**File:** `api/main.py`

**Update lifespan:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    global copilot, db_manager, cache_service
    
    try:
        # Get agents configuration from settings
        agents_config = settings.get_agents_config()
        
        # Initialize AML Copilot with config
        copilot = AMLCopilot(agents_config=agents_config)
        
        # ... rest of initialization ...
        
        yield
    finally:
        # ... cleanup ...
```

---

## 🎯 Phase 2: Context-Aware Queries

### 2.1 Create QueryContext Model
**File:** `api/models.py`

**Add:**
```python
class QueryContext(BaseModel):
    """Context for a query."""
    cif_no: str = Field(..., description="Customer ID (always required)")
    alert_id: Optional[str] = Field(None, description="Alert ID if reviewing alert")
    investigation_id: Optional[str] = Field(None, description="Investigation ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "cif_no": "C000001",
                "alert_id": "ALT12345",
                "investigation_id": "INV789"
            }
        }
```

---

### 2.2 Update QueryRequest Model
**File:** `api/models.py`

**Change:**
```python
class QueryRequest(BaseModel):
    """Request model for querying the AML Copilot."""
    
    query: str = Field(..., description="Natural language query", min_length=1)
    context: QueryContext = Field(..., description="Query context (customer, alert, etc.)")
    user_id: str = Field(..., description="User ID")  # TODO: Extract from JWT in Phase 6
    session_id: str = Field(..., description="Session ID for conversation tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the customer's risk score?",
                "context": {
                    "cif_no": "C000001",
                    "alert_id": "ALT12345"
                },
                "user_id": "jane_doe",
                "session_id": "investigation_abc123"
            }
        }
```

---

### 2.3 Update AMLCopilotState
**File:** `agents/state.py`

**Add:**
```python
class AMLCopilotState(TypedDict):
    """State for the AML Copilot workflow."""
    
    # ... existing fields ...
    
    # NEW: Context
    context: Dict[str, Any]  # Contains cif_no, alert_id, investigation_id
```

---

### 2.4 Remove CIF Extraction from Intent Mapper
**File:** `agents/intent_mapper.py`

**Remove `_extract_cif()` method entirely.**

**Update process method to use context:**
```python
def process(self, state: AMLCopilotState) -> Dict[str, Any]:
    """Process intent mapping with context."""
    
    # Get CIF from context instead of extracting
    cif_no = state.get("context", {}).get("cif_no")
    if not cif_no:
        return {"error": "Missing cif_no in context"}
    
    # ... rest of processing uses cif_no from context ...
```

---

### 2.5 Update API Endpoint
**File:** `api/main.py`

**Update query endpoint:**
```python
@app.post("/api/query", response_model=QueryResponse)
async def query_copilot(request: QueryRequest):
    """Query the AML Copilot with context."""
    
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")
    
    try:
        result = copilot.query(
            user_query=request.query,
            context=request.context.dict(),
            session_id=request.session_id,
            user_id=request.user_id,
        )
        
        return QueryResponse(
            response=result.get("response", ""),
            session_id=request.session_id,
            compliance_analysis=result.get("compliance_analysis"),
            retrieved_data=result.get("retrieved_data"),
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 2.6 Update AMLCopilot.query() Method
**File:** `agents/graph.py`

**Update:**
```python
def query(
    self,
    user_query: str,
    context: Dict[str, Any],
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Process query with automatic conversation continuity.
    
    Args:
        user_query: Natural language query
        context: Context dict with cif_no, alert_id, etc.
        session_id: Session identifier
        user_id: User identifier
    
    Returns:
        Query results with full conversation history
    """
    # Create thread_id for Redis checkpointer
    thread_id = f"{user_id}_{session_id}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Build state with context
    state = {
        "messages": [
            {
                "role": "user",
                "content": user_query,
                "timestamp": datetime.now().isoformat()
            }
        ],
        "user_query": user_query,
        "context": context,  # NEW: Include context in state
        "next_agent": "coordinator",
        "current_step": "initialized",
        "session_id": session_id,
        "started_at": datetime.now().isoformat(),
    }
    
    # Invoke with checkpointing (RedisSaver auto-loads previous messages!)
    final_state = self.graph.invoke(state, config=config)
    
    return {
        "response": final_state.get("final_response"),
        "compliance_analysis": final_state.get("compliance_analysis"),
        "retrieved_data": final_state.get("retrieved_data"),
        "messages": final_state.get("messages", []),
        "session_id": session_id,
    }
```

---

## 🗺️ Phase 3: Materialized Typology Mappings

### 3.1 Create Typology Mappings File
**File:** `data/typology_mappings.json` (new file)

```json
{
  "version": "1.0",
  "description": "Feature to Red Flag to Typology mappings for AML compliance",
  "typologies": {
    "structuring": {
      "name": "Structuring / Smurfing",
      "description": "Breaking up large transactions to avoid reporting thresholds",
      "severity": "high",
      "red_flags": [
        {
          "feature_group": "cash_activity",
          "features": ["count_cash_intensive_txn_w0_90", "sum_cash_deposits_w0_30"],
          "condition": "count > 10 AND avg_amount < 10000",
          "description": "Multiple cash deposits just below reporting threshold"
        },
        {
          "feature_group": "transaction_patterns",
          "features": ["avg_txn_amount_w0_30", "count_txn_w0_30"],
          "condition": "avg_amount BETWEEN 9000 AND 9900 AND count > 5",
          "description": "Consistent transaction amounts near $10k threshold"
        }
      ],
      "regulatory_references": ["FATF Recommendation 10", "BSA Section 5318(g)"]
    },
    "trade_based_money_laundering": {
      "name": "Trade-Based Money Laundering (TBML)",
      "description": "Using trade transactions to disguise illicit funds",
      "severity": "high",
      "red_flags": [
        {
          "feature_group": "international_activity",
          "features": ["count_intl_txn_w0_90", "sum_intl_txn_w0_90"],
          "condition": "count > 20 AND sum > 500000",
          "description": "High volume international transactions"
        }
      ],
      "regulatory_references": ["FATF Recommendation 32"]
    },
    "layering": {
      "name": "Layering",
      "description": "Complex transactions to obscure source of funds",
      "severity": "medium",
      "red_flags": [
        {
          "feature_group": "transaction_patterns",
          "features": ["distinct_destination_countries_w0_90", "count_txn_w0_90"],
          "condition": "distinct_countries > 5 AND count > 50",
          "description": "Transactions to multiple countries suggesting layering"
        }
      ],
      "regulatory_references": ["FATF Recommendation 10"]
    }
  }
}
```

---

### 3.2 Create TypologyService
**File:** `db/services/typology_service.py` (new file)

```python
"""Service for typology detection and analysis."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class TypologyService:
    """Service for detecting AML typologies based on feature patterns."""
    
    def __init__(self, mappings_path: str = "data/typology_mappings.json"):
        """Initialize with typology mappings."""
        self.mappings_path = Path(mappings_path)
        self.typologies = self._load_mappings()
    
    def _load_mappings(self) -> Dict[str, Any]:
        """Load typology mappings from JSON."""
        with open(self.mappings_path) as f:
            data = json.load(f)
        return data.get("typologies", {})
    
    def analyze_features(
        self,
        features: Dict[str, Any],
        threshold: str = "medium"
    ) -> Dict[str, Any]:
        """Analyze features and detect matching typologies.
        
        Args:
            features: Dict of feature_name -> value
            threshold: Minimum severity (low, medium, high)
        
        Returns:
            Dict with detected typologies and explanations
        """
        detected = []
        
        for typology_id, typology in self.typologies.items():
            # Check severity threshold
            if not self._meets_threshold(typology.get("severity"), threshold):
                continue
            
            # Check red flags
            matched_flags = []
            for red_flag in typology.get("red_flags", []):
                if self._check_red_flag(red_flag, features):
                    matched_flags.append(red_flag)
            
            # If any red flags matched, include typology
            if matched_flags:
                detected.append({
                    "typology_id": typology_id,
                    "typology_name": typology["name"],
                    "description": typology["description"],
                    "severity": typology["severity"],
                    "matched_red_flags": [
                        {
                            "description": flag["description"],
                            "features": flag["features"]
                        }
                        for flag in matched_flags
                    ],
                    "regulatory_references": typology.get("regulatory_references", [])
                })
        
        return {
            "detected_typologies": detected,
            "count": len(detected),
            "highest_severity": self._get_highest_severity(detected)
        }
    
    def _check_red_flag(self, red_flag: Dict, features: Dict[str, Any]) -> bool:
        """Check if red flag conditions are met."""
        # Simplified: Check if relevant features exist
        # TODO: Implement actual condition parsing (e.g., "count > 10")
        required_features = red_flag.get("features", [])
        return all(feature in features for feature in required_features)
    
    def _meets_threshold(self, severity: str, threshold: str) -> bool:
        """Check if severity meets threshold."""
        severity_levels = {"low": 1, "medium": 2, "high": 3}
        return severity_levels.get(severity, 0) >= severity_levels.get(threshold, 0)
    
    def _get_highest_severity(self, typologies: List[Dict]) -> Optional[str]:
        """Get highest severity from detected typologies."""
        if not typologies:
            return None
        severities = [t.get("severity") for t in typologies]
        if "high" in severities:
            return "high"
        elif "medium" in severities:
            return "medium"
        return "low"
```

---

### 3.3 Integrate with Data Retrieval Agent
**File:** `agents/data_retrieval.py`

**Add to imports:**
```python
from db.services.typology_service import TypologyService
```

**Update agent:**
```python
class DataRetrievalAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = ChatOpenAI(...)
        self.typology_service = TypologyService()  # NEW
    
    def process(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Process data retrieval with typology analysis."""
        
        # ... existing data retrieval ...
        
        # NEW: Analyze for typologies
        if retrieved_data:
            typology_analysis = self.typology_service.analyze_features(
                features=retrieved_data,
                threshold="medium"
            )
            
            return {
                "retrieved_data": retrieved_data,
                "typology_analysis": typology_analysis,  # NEW
                "next_agent": "compliance_expert"
            }
```

---

### 3.4 Update Compliance Expert to Use Typologies
**File:** `agents/compliance_expert.py`

**Update process method:**
```python
def process(self, state: AMLCopilotState) -> Dict[str, Any]:
    """Process compliance analysis with typology guidance."""
    
    # Get typology analysis from state
    typology_analysis = state.get("typology_analysis", {})
    detected_typologies = typology_analysis.get("detected_typologies", [])
    
    # Build prompt with typology context
    if detected_typologies:
        typology_context = "\n".join([
            f"- {t['typology_name']}: {t['description']} (Severity: {t['severity']})"
            for t in detected_typologies
        ])
        enhanced_prompt = f"""
{self.prompt}

DETECTED TYPOLOGIES:
{typology_context}

Focus your analysis on these detected patterns.
"""
    else:
        enhanced_prompt = self.prompt
    
    # ... rest of processing ...
```

---

## 🔍 Phase 4: Review System (Self-Review + Human Review)

### 4.1 Create Review Models
**File:** `api/models.py`

**Add:**
```python
from enum import Enum

class ResponseStatus(str, Enum):
    """Status of agent response after review."""
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    REJECTED = "rejected"

class ReviewResult(BaseModel):
    """Result of response review."""
    status: ResponseStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    issues: List[str] = []
    suggestions: List[str] = []
    requires_human: bool = False

class AgentResponse(BaseModel):
    """Agent response with review metadata."""
    content: str
    review: Optional[ReviewResult] = None
    version: int = 1
```

---

### 4.2 Create Review Logic
**File:** `agents/review.py` (new file)

```python
"""Self-review logic for agent responses."""

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from .state import AMLCopilotState
from api.models import ReviewResult, ResponseStatus


REVIEW_PROMPT = """You are a quality control reviewer for AML compliance responses.

Review the following response for:
1. Accuracy - Are facts correct?
2. Completeness - Is anything missing?
3. Compliance - Does it follow regulations?
4. Clarity - Is it understandable?
5. Risk level - Does it need human review?

RESPONSE TO REVIEW:
{response}

RETRIEVED DATA:
{data}

COMPLIANCE ANALYSIS:
{analysis}

Provide review in JSON format:
{{
    "status": "approved|needs_revision|needs_human_review",
    "confidence": 0.0-1.0,
    "issues": ["issue 1", "issue 2"],
    "suggestions": ["suggestion 1"],
    "requires_human": true/false
}}
"""


class ReviewAgent:
    """Agent for reviewing responses."""
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
    
    def self_review_response(self, state: AMLCopilotState) -> Dict[str, Any]:
        """Self-review the final response.
        
        Args:
            state: Current workflow state
        
        Returns:
            Updated state with review results
        """
        response = state.get("final_response", "")
        retrieved_data = state.get("retrieved_data", {})
        compliance_analysis = state.get("compliance_analysis", {})
        
        # Build review prompt
        prompt = REVIEW_PROMPT.format(
            response=response,
            data=retrieved_data,
            analysis=compliance_analysis
        )
        
        # Get review
        review_result = self.llm.invoke(prompt)
        
        # Parse review (simplified - add proper JSON parsing)
        review = ReviewResult(
            status=ResponseStatus.APPROVED,
            confidence=0.85,
            issues=[],
            suggestions=[],
            requires_human=False
        )
        
        return {
            "review_result": review,
            "next_agent": "end" if review.status == ResponseStatus.APPROVED else "compliance_expert"
        }


def create_review_node():
    """Create review node function."""
    agent = ReviewAgent()
    return agent.self_review_response
```

---

### 4.3 Add Review Node to Graph
**File:** `agents/graph.py`

**Add imports:**
```python
from .review import create_review_node
```

**Update graph creation:**
```python
def create_aml_copilot_graph(agents_config: AgentsConfig, checkpointer=None):
    """Create graph with review node."""
    workflow = StateGraph(AMLCopilotState)
    
    # Add existing nodes
    workflow.add_node("coordinator", create_coordinator_node(agents_config.coordinator))
    workflow.add_node("intent_mapper", create_intent_mapper_node(agents_config.intent_mapper))
    workflow.add_node("data_retrieval", create_data_retrieval_node(agents_config.data_retrieval))
    workflow.add_node("compliance_expert", create_compliance_expert_node(agents_config.compliance_expert))
    
    # NEW: Add review node
    workflow.add_node("review", create_review_node())
    
    # Update edges to include review
    workflow.add_edge("compliance_expert", "review")
    workflow.add_conditional_edges(
        "review",
        route_after_review,  # NEW routing function
        {
            "end": END,
            "compliance_expert": "compliance_expert",  # Needs revision
        }
    )
    
    # ... rest of workflow ...
```

---

### 4.4 Add Review API Endpoint
**File:** `api/main.py`

**Add:**
```python
@app.post("/api/review/{session_id}/approve")
async def approve_response(session_id: str):
    """Human approves a response that needed review."""
    # TODO: Implement approval logic
    return {"status": "approved", "session_id": session_id}

@app.post("/api/review/{session_id}/reject")
async def reject_response(session_id: str, feedback: str):
    """Human rejects a response that needed review."""
    # TODO: Implement rejection and retry logic
    return {"status": "rejected", "session_id": session_id}
```

---

## 💾 Phase 5: Redis Session Integration (Already Decided!)

### 5.1 Install RedisSaver
**Add to pyproject.toml:**
```toml
[tool.poetry.dependencies]
langgraph-checkpoint-redis = "^0.1.0"  # Or latest version
```

**Run:**
```bash
poetry install
```

---

### 5.2 Verify Settings (Already Done in Phase 1.2)
**File:** `config/settings.py`

Ensure these exist:
```python
redis_host: str = "localhost"
redis_port: int = 6379
redis_db_checkpoints: int = 1  # For LangGraph
redis_db_cache: int = 0  # For data caching
```

---

### 5.3 Update CacheService to Use Correct DB
**File:** `db/services/cache_service.py`

**Update Redis connection:**
```python
from config.settings import settings

class CacheService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db_cache,  # Use db=0 for cache
            decode_responses=True
        )
```

---

### 5.4 Verify AMLCopilot Integration (Already Done in Phase 1.5)
**File:** `agents/graph.py`

Should already have:
```python
from langgraph.checkpoint.redis import RedisSaver

class AMLCopilot:
    def __init__(self, agents_config: AgentsConfig):
        self.checkpointer = RedisSaver.from_conn_info(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db_checkpoints,  # db=1
        )
        self.graph = create_aml_copilot_graph(
            agents_config=agents_config,
            checkpointer=self.checkpointer
        )
```

---

## 🔐 Phase 6: JWT Authentication (FUTURE - Not MVP)

### 6.1 Add JWT Dependencies
```bash
poetry add python-jose[cryptography] passlib[bcrypt]
```

---

### 6.2 Create Auth Module
**File:** `api/auth.py` (new file)

```python
"""JWT authentication for API."""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = "your-secret-key"  # TODO: Move to settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract user_id from JWT token."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

### 6.3 Update API Endpoints
**File:** `api/main.py`

```python
from api.auth import get_current_user

@app.post("/api/query", response_model=QueryResponse)
async def query_copilot(
    request: QueryRequest,
    user_id: str = Depends(get_current_user)  # Extract from JWT
):
    """Query with JWT auth."""
    # No longer need user_id in request body!
    result = copilot.query(
        user_query=request.query,
        context=request.context.dict(),
        session_id=request.session_id,
        user_id=user_id,  # From JWT
    )
    return QueryResponse(**result)
```

---

### 6.4 Remove user_id from QueryRequest
**File:** `api/models.py`

```python
class QueryRequest(BaseModel):
    """Request model (JWT version)."""
    query: str
    context: QueryContext
    session_id: str
    # user_id REMOVED - extracted from JWT token
```

---

## 📝 Summary

### Implementation Order:
1. ✅ **Phase 1: DI & Configuration** - MUST DO FIRST (blocks everything)
2. ✅ **Phase 2: Context-Aware Queries** - High value, simplifies everything
3. ✅ **Phase 5: Redis Sessions** - Quick win (mostly done in Phase 1)
4. ✅ **Phase 3: Typology Mappings** - Medium priority
5. ✅ **Phase 4: Review System** - Safety net
6. ⏭️ **Phase 6: JWT Auth** - Future enhancement

### Future Enhancements (Not in MVP):
- Cross-session memory (Redis → PostgreSQL persistence)
- Advanced typology condition parsing
- Human review UI
- Audit trail dashboard
- Rate limiting
- API versioning

---

## 🚀 Ready to Start?

**Recommended first step:**
```bash
# Create agent config file
touch config/agent_config.py
```

Let's implement Phase 1.1: Create Agent Configuration Models!
