# AML Copilot - Multi-Agent Compliance Assistant

## Project Overview

AML Copilot is an intelligent multi-agent system designed to assist AML (Anti-Money Laundering) analysts with compliance investigations, alert reviews, and regulatory reporting. The system operates in two distinct modes:

### 1. Copilot Mode (Analytical Assistant)
Helps analysts by:
- Answering AML compliance questions
- Retrieving and analyzing customer/transaction data
- Providing regulatory guidance and best practices
- Explaining typologies and red flags
- Supporting investigation workflows

### 2. Autonomous Review Mode (Decision Support)
Provides autonomous analysis:
- L2 alert disposition recommendations (CLOSE/ESCALATE/FILE_SAR)
- SAR narrative generation (FinCEN-compliant)
- Transaction pattern analysis for suspicious activity
- Regulatory threshold evaluation

## Architecture

### Multi-Agent System (LangGraph)

The system uses a **state-driven multi-agent architecture** with specialized agents:

1. **CoordinatorAgent** (agents/subagents/coordinator.py:15)
   - Entry point for all queries
   - Routes to appropriate agents based on intent
   - Distinguishes between copilot vs autonomous review mode
   - Message History: Last 3 messages (basic continuity)

2. **IntentMapperAgent** (agents/subagents/intent_mapper.py)
   - Classifies user intent and extracts entities
   - Determines required data retrieval
   - Message History: Last 10 messages (reference resolution)

3. **DataRetrievalAgent** (agents/subagents/data_retrieval.py)
   - Executes database queries
   - Fetches customer, transaction, and alert data
   - Message History: None (pure executor)

4. **ComplianceExpertAgent** (agents/subagents/compliance_expert.py:15)
   - Provides AML domain analysis
   - Synthesizes responses for copilot mode
   - Message History: ALL messages (comprehensive analysis)

5. **ReviewAgent** (agents/subagents/review_agent.py:15)
   - QA for compliance expert outputs
   - Can request additional data or refinement
   - Message History: ALL messages (quality assurance)

6. **AMLAlertReviewerAgent** (agents/subagents/aml_alert_reviewer.py:17)
   - **NEW**: Autonomous alert review and SAR generation
   - Disposition decisions (CLOSE/ESCALATE/FILE_SAR)
   - Transaction pattern analysis
   - Message History: ALL messages (full investigation context)

### Agent Workflow

```
Copilot Mode Flow:
START → Coordinator → IntentMapper → DataRetrieval → ComplianceExpert → ReviewAgent → END

Autonomous Review Flow:
START → Coordinator → AMLAlertReviewerAgent → END
```

### Technology Stack

- **Framework**: LangGraph (agent orchestration)
- **LLM**: OpenAI GPT-4o / GPT-4o-mini (configurable per agent)
- **Database**: PostgreSQL (customer/transaction data)
- **Cache/State**: Redis (2 databases: cache + LangGraph checkpoints)
- **API**: FastAPI (REST endpoints)
- **Config**: Pydantic Settings (environment-based configuration)

## Key Design Patterns

### 1. Repository Pattern
All database access goes through repository layer:
- `db/repositories/` - Clean separation of data access
- Dependency injection via FastAPI
- No direct SQL in agents

### 2. Message History Control
Each agent has configurable message history limits:
- **None**: ALL messages (ComplianceExpert, ReviewAgent, AMLAlertReviewer)
- **0**: NO messages (DataRetrieval - pure executor)
- **3**: Last 3 messages (Coordinator - basic continuity)
- **10**: Last 10 messages (IntentMapper - reference resolution)

Rationale: Balance context awareness with token efficiency

### 3. State Management
- **Shared State**: `AMLCopilotState` (agents/state.py:41) - All agents read/write
- **State Persistence**: Redis-backed checkpoints for conversation continuity
- **Typed Updates**: `AgentResponse` TypedDict ensures type-safe state updates

### 4. Configuration-Driven
- Per-agent LLM models and parameters (config/settings.py:102)
- Environment-based configuration (.env)
- Separation of dev/test/prod settings

## Directory Structure

```
aml_copilot/
├── agents/                    # Multi-agent system
│   ├── base_agent.py         # Abstract base class for all agents
│   ├── copilot.py            # Main AMLCopilot orchestrator
│   ├── graph.py              # LangGraph workflow definition
│   ├── state.py              # Shared state schema
│   ├── prompts/              # Agent prompts (organized by agent)
│   └── subagents/            # Individual agent implementations
├── api/                       # FastAPI REST API
│   └── main.py               # API endpoints
├── config/                    # Configuration
│   ├── agent_config.py       # Agent-specific configs
│   └── settings.py           # Application settings
├── db/                        # Database layer
│   ├── models.py             # SQLAlchemy ORM models
│   ├── repositories/         # Data access layer (repository pattern)
│   └── session.py            # Database session management
├── services/                  # Business logic
├── tests/                     # Test suite
└── notebooks/                # Jupyter notebooks for testing

.claude/                       # Claude Code workspace config
├── agents/                    # Custom Claude agents
│   ├── aml-product-owner.md  # AML domain expert for development
│   └── (other agents)        # Architecture/code review agents
└── commands/                  # Custom slash commands (if any)
```

## Database Schema (PostgreSQL)

Key tables:
- **customers**: Customer master data (CIF, name, risk_rating, etc.)
- **alerts**: AML alerts (alert_id, cif_no, alert_type, status, etc.)
- **transactions**: Transaction data (txn_id, cif_no, amount, date, etc.)
- **transactions_features**: Pre-computed transaction features for ML/analysis

Note: Schema defined in `db/models.py` using SQLAlchemy ORM

## Configuration Files

- **config/settings.py:17**: Main application settings (database, Redis, LLM configs)
- **config/agent_config.py:7**: Agent configuration models
- **.env**: Environment variables (not in repo - see .env.example)
- **docker-compose.yml:1**: Local development stack (Postgres + Redis)

## Development Workflow

### Working with Agents

When modifying agents:
1. **Read the base agent class first**: `agents/base_agent.py`
2. **Check state schema**: `agents/state.py` for available state fields
3. **Review prompts**: Each agent has prompts in `agents/prompts/`
4. **Test message history**: Ensure appropriate `message_history_limit` in config
5. **Update graph if needed**: `agents/graph.py` for routing changes

### Testing Approach

- **Unit Tests**: Test individual agent logic (tests/)
- **Integration Tests**: Test agent workflows end-to-end
- **Notebooks**: Interactive testing and exploration (notebooks/)
- **Phase Tests**: Validated test suites per development phase (notebooks/phase*_validated_tests.ipynb)

### Adding New Agents

1. Create agent class in `agents/subagents/new_agent.py` inheriting from `BaseAgent`
2. Implement `__call__(state: AMLCopilotState) -> AgentResponse`
3. Create prompts in `agents/prompts/new_agent_prompt.py`
4. Add config to `config/agent_config.py` (AgentsConfig)
5. Add settings to `config/settings.py` (model, temperature, etc.)
6. Update graph in `agents/graph.py` (add node, routing)
7. Export from `agents/subagents/__init__.py`

### Adding New Tools/Data Access

1. Define repository method in appropriate repository (e.g., `db/repositories/alert_repository.py`)
2. Add to dependency injection in `api/main.py`
3. Make available to DataRetrievalAgent via tool mapping
4. Update IntentMapper prompt to recognize new data needs

## Common Tasks

### Run the API server
```bash
poetry run uvicorn api.main:app --reload
```

### Run tests
```bash
poetry run pytest tests/ -v
```

### Start local databases
```bash
docker-compose up -d
```

### Access Redis CLI
```bash
docker exec -it aml_copilot-redis-1 redis-cli
```

## Important Implementation Notes

### Copilot Mode vs Autonomous Review Mode

The **Coordinator** distinguishes modes based on query intent (agents/prompts/coordinator_prompt.py:13):

**Copilot Mode Indicators**:
- Questions: "What are red flags...?"
- Guidance requests: "Help me understand..."
- Data requests: "Show me transactions for..."

**Autonomous Review Mode Indicators**:
- Decision requests: "Review alert #123"
- Disposition requests: "Should I file a SAR?"
- Generation requests: "Draft a SAR for..."

This distinction is CRITICAL for routing to the correct agent.

### Message History Philosophy

Different agents need different context:
- **Comprehensive analyzers** (ComplianceExpert, ReviewAgent, AMLAlertReviewer): ALL messages
  - Need full investigation context for proper analysis
- **Reference resolvers** (IntentMapper): Last 10 messages
  - Need recent context to resolve "show me more" or "what about..."
- **Basic continuity** (Coordinator): Last 3 messages
  - Need just enough to detect follow-ups
- **Pure executors** (DataRetrieval): NO messages
  - Execute based on intent only, no conversation needed

### State Persistence

- Redis DB 0: Data caching (customer/transaction data)
- Redis DB 1: LangGraph checkpoints (conversation state)
- Setting: `enable_redis_checkpointing` (config/settings.py:33)

### Review System

The ReviewAgent provides adaptive QA:
- **passed**: Response is good → END
- **needs_data**: Missing information → route to IntentMapper
- **needs_refinement**: Quality issues → route back to ComplianceExpert
- **needs_clarification**: Ambiguous → ask user
- **human_review**: High-risk → escalate

Max attempts: 3 (config/settings.py:61)

## Claude Code Workspace

### Custom Agents (.claude/agents/)

- **aml-product-owner**: AML domain expert for BUILD guidance
  - Use when: Designing features, reviewing prompts, validating compliance
  - NOT for: Operational alert review (that's in the project)

### When to Use aml-product-owner Agent

- "How should I design this feature?"
- "Review this prompt for regulatory accuracy"
- "What edge cases should I test?"
- "What are the FinCEN requirements for X?"
- "Is this architecture compliant with BSA/AML?"

## Regulatory Context

This system must comply with:
- **Bank Secrecy Act (BSA)**: Recordkeeping and reporting requirements
- **FinCEN SAR Reporting**: 30-day filing deadline, $5K+ threshold for suspicious activity
- **USA PATRIOT Act**: Customer identification and due diligence
- **FATF Recommendations**: Risk-based approach, beneficial ownership

All outputs must be:
- Audit-ready with defensible rationale
- Properly documented for regulatory review
- Compliant with reporting thresholds and timelines

## Git Workflow

Current branch: `main`
Recent development phases:
- Phase 4: Adaptive Review System with ReviewAgent
- Phase 5: Redis Database Separation

When committing:
- Use descriptive messages indicating phase or feature
- Include Claude Code co-authorship (automatic via git hooks)
- Run tests before major commits

## Contact & Context

This is an internal AML compliance tool for financial institutions. The system is designed to augment, not replace, human AML analysts. All high-risk decisions require human review and approval.
