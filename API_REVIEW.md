# API Layer Review - AML Copilot

## 🔍 Current State

### ✅ What's Implemented

1. **FastAPI Application** (`api/main.py`)
   - Basic REST endpoints for querying the copilot
   - Health check endpoint with dependency verification
   - Cache management endpoint
   - Tool listing endpoint
   - Proper error handling with custom error responses

2. **Pydantic Models** (`api/models.py`)
   - `QueryRequest` - user query with optional session ID
   - `QueryResponse` - response with compliance analysis and data
   - `ComplianceAnalysisResponse` - structured compliance output
   - `HealthResponse` - health check results
   - `ErrorResponse` - error formatting

3. **Agent Integration**
   - Global `AMLCopilot` instance created at startup
   - Lifespan context manager for proper initialization/shutdown
   - Basic error handling for failed queries

4. **Configuration** (`config/settings.py`)
   - Environment-based settings using `pydantic-settings`
   - Database, Redis, LLM, and agent configuration
   - Global `settings` singleton instance

### ❌ Critical Issues - Missing Dependency Injection & Configuration

#### **Problem 1: Hardcoded Model Names**
Each agent hardcodes its LLM model and initialization:

```python
# agents/coordinator.py
class CoordinatorAgent:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

# agents/intent_mapper.py
class IntentMappingAgent:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
```

**Issues:**
- Models are hardcoded to `gpt-4o-mini` (not configurable from settings)
- No way to change models at startup
- Temperature values hardcoded
- Settings has `llm_model: str = "gpt-4"` but it's **never used** by agents

#### **Problem 2: No DI Pattern for Agent Creation**
The `AMLCopilot` class creates agents with hardcoded defaults:

```python
# agents/graph.py
class AMLCopilot:
    def __init__(self):
        self.graph = create_aml_copilot_graph()
```

No way to pass configuration to agents. The graph creation uses factory functions that create agents with hardcoded parameters:

```python
# agents/graph.py
workflow.add_node("coordinator", create_coordinator_node())  # No config!
```

#### **Problem 3: API Startup is Inflexible**
```python
# api/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    copilot = AMLCopilot()  # Only one way to initialize
```

#### **Problem 4: Tools Don't Use Dependency Injection**
Data retrieval agents create tools without DI:
```python
# No access to service layer through DI
# Hard to test, hard to swap implementations
```

---

## 🎯 Required Changes

### 1. **Agent Configuration Model**

Create `config/agent_config.py`:
```python
class AgentConfig(BaseModel):
    """Configuration for individual agents."""
    model_name: str
    temperature: float
    max_retries: int
    timeout: int

class AgentsConfig(BaseModel):
    """Configuration for all agents."""
    coordinator: AgentConfig
    intent_mapper: AgentConfig
    data_retrieval: AgentConfig
    compliance_expert: AgentConfig
    use_async: bool = False
```

### 2. **Update Settings**

Extend `config/settings.py` to include agent configurations:
```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Agent-specific configurations
    coordinator_model: str = "gpt-4o-mini"
    coordinator_temp: float = 0.0
    intent_mapper_model: str = "gpt-4o-mini"
    intent_mapper_temp: float = 0.0
    data_retrieval_model: str = "gpt-4o-mini"
    data_retrieval_temp: float = 0.0
    compliance_expert_model: str = "gpt-4o-mini"
    compliance_expert_temp: float = 0.3
```

### 3. **Dependency Injection for Agents**

Modify agent constructors to accept DI:
```python
class CoordinatorAgent:
    def __init__(self, config: AgentConfig):
        self.llm = ChatOpenAI(model=config.model_name, temperature=config.temperature)
        self.max_retries = config.max_retries
```

### 4. **Update Graph Creation**

Pass configuration through the graph:
```python
def create_aml_copilot_graph(agents_config: AgentsConfig):
    """Create graph with injected agent configs."""
    coordinator = CoordinatorAgent(config=agents_config.coordinator)
    intent_mapper = IntentMappingAgent(config=agents_config.intent_mapper)
    # ...
```

### 5. **Update AMLCopilot Class**

```python
class AMLCopilot:
    def __init__(self, agents_config: AgentsConfig):
        self.config = agents_config
        self.graph = create_aml_copilot_graph(agents_config)
```

### 6. **Update API Startup**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global copilot
    
    logger.info("Starting AML Copilot API...")
    try:
        # Get agent configurations from settings
        agents_config = AgentsConfig(
            coordinator=AgentConfig(
                model_name=settings.coordinator_model,
                temperature=settings.coordinator_temp,
                # ...
            ),
            # ... other agents ...
        )
        
        copilot = AMLCopilot(agents_config=agents_config)
        logger.info(f"✓ AML Copilot initialized with models:")
        logger.info(f"  - Coordinator: {agents_config.coordinator.model_name}")
        logger.info(f"  - Intent Mapper: {agents_config.intent_mapper.model_name}")
        # ...
    except Exception as e:
        logger.error(f"✗ Failed to initialize agent: {e}")
        raise
    
    yield
    
    # Shutdown...
```

---

## 📋 Implementation Plan

1. **Create AgentConfig models** in `config/agent_config.py`
2. **Update Settings** to include per-agent configs
3. **Update each agent class** to accept config via DI
4. **Update graph creation functions** to accept configs
5. **Update AMLCopilot class** to accept and propagate configs
6. **Update API lifespan** to read from settings and create copilot with configs
7. **Add .env example** with all agent model configurations
8. **Add tests** to verify DI is working correctly

---

## 🔄 Data Flow With DI

```
API Startup
  ↓
Load settings from .env / environment
  ↓
Create AgentsConfig from settings
  ↓
AMLCopilot.__init__(agents_config)
  ↓
create_aml_copilot_graph(agents_config)
  ↓
CoordinatorAgent(config.coordinator)
IntentMappingAgent(config.intent_mapper)
DataRetrievalAgent(config.data_retrieval)
ComplianceExpertAgent(config.compliance_expert)
  ↓
Each agent creates LLM with configured model/temperature
  ↓
Graph ready to process queries
```

---

## ✨ Benefits

✅ **Model Flexibility** - Change models via environment variables  
✅ **Configuration as Code** - All settings in one place  
✅ **Testability** - Easy to inject test configs  
✅ **Runtime Configuration** - Different models for different environments  
✅ **Clear Intent** - Dependencies are explicit  
✅ **Future-Proof** - Easy to add more agent configs later  

---

## ❌ What Happens Without This

- 🔴 Can't change which OpenAI model is used without code changes
- 🔴 Can't use cheaper models in non-production
- 🔴 Can't easily test with mock LLMs
- 🔴 Hard to debug agent behavior issues
- 🔴 Temperature values can't be adjusted per-environment
- 🔴 Agents tightly coupled to hardcoded config
