# AML Copilot - Multi-Agent Compliance Assistant

## 🚧 ACTIVE DEVELOPMENT - New Architecture Migration (Dec 2024)

**Current Branch**: `feature/langchain-architecture-migration`
**Status**: Implementing 3-task modernization plan
**Plan Document**: `/Users/souley/.claude/plans/fizzy-stargazing-kitten.md`

### Migration Goals
1. **Task 1**: Infrastructure (middleware, LangSmith, Agent UI) - IN PROGRESS
2. **Task 2**: Modern LangChain agent with sub-agents as tools
3. **Task 3**: LangSmith evaluation framework

**See "Active Development Tasks" section below for current progress**

---

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

### 1. Modular Prompt Architecture (NEW)
Prompts are built from reusable components:
- `agents/prompts/components/red_flag_catalog.py` - AML red flag definitions
- `agents/prompts/components/typology_library.py` - Money laundering typologies
- `agents/prompts/components/regulatory_references.py` - BSA/AML regulations

**Benefits**:
- Single source of truth for domain knowledge
- Independent domain expert review of each component
- Shared knowledge across Compliance Expert and AML Alert Reviewer
- Easy testing with different component versions

**Status**: Components marked as `PLACEHOLDER` - need expert review before production

### 2. Repository Pattern
All database access goes through repository layer:
- `db/repositories/` - Clean separation of data access
- Dependency injection via FastAPI
- No direct SQL in agents

### 3. Message History Control
Each agent has configurable message history limits:
- **None**: ALL messages (ComplianceExpert, ReviewAgent, AMLAlertReviewer)
- **0**: NO messages (DataRetrieval - pure executor)
- **3**: Last 3 messages (Coordinator - basic continuity)
- **10**: Last 10 messages (IntentMapper - reference resolution)

Rationale: Balance context awareness with token efficiency

### 4. ML Model Integration (NEW)
The system interprets pre-computed ML outputs rather than computing features:

**Data Flow**:
```
ML Model Service → Feature Store → Data Service → Compliance Expert → Review
```

**ML Output Structure** (agents/state.py:65):
- Daily risk score trends
- Pre-computed feature values (transaction patterns, volumes)
- Red flag confidence scores (e.g., "transactions_below_threshold": 0.95)
- Typology likelihood assessments (e.g., "structuring": 0.85)
- Attribution chain: Typology → Red Flags → Features

**Tools** (tools/ml_output_tools.py):
- `get_ml_risk_assessment(cif_no)` - Retrieve complete ML assessment
- `get_feature_importance(cif_no, typology)` - Explain feature contributions

**Current Status**: Uses test fixtures (`tests/fixtures/ml_model_fixtures.py`)
- Marked as `MOCK_DATA` - needs ML service integration before production
- 5 realistic scenarios: structuring, layering, low_risk, trade_based_ml, incomplete_data

### 5. State Management
- **Shared State**: `AMLCopilotState` (agents/state.py:91) - All agents read/write
- **State Persistence**: Redis-backed checkpoints for conversation continuity
- **Typed Updates**: `AgentResponse` TypedDict ensures type-safe state updates
- **ML Outputs**: `ml_model_output` field added to state schema

### 6. Configuration-Driven
- Per-agent LLM models and parameters (config/settings.py:102)
- Environment-based configuration (.env)
- Separation of dev/test/prod settings

## Directory Structure

```
aml_copilot/
├── agents/                    # Multi-agent system
│   ├── base_agent.py         # Abstract base class (with shared JSON parsing)
│   ├── copilot.py            # Main AMLCopilot orchestrator
│   ├── graph.py              # LangGraph workflow definition
│   ├── state.py              # Shared state schema (includes ML types)
│   ├── prompts/              # Agent prompts
│   │   ├── components/       # ✨ NEW: Reusable prompt components
│   │   │   ├── red_flag_catalog.py       # PLACEHOLDER - needs expert review
│   │   │   ├── typology_library.py       # PLACEHOLDER - needs expert review
│   │   │   └── regulatory_references.py  # PLACEHOLDER - needs expert review
│   │   └── [agent]_prompt.py # Per-agent prompts
│   └── subagents/            # Individual agent implementations
├── api/                       # FastAPI REST API
│   └── main.py               # API endpoints
├── config/                    # Configuration
│   ├── agent_config.py       # Agent-specific configs
│   └── settings.py           # Application settings
├── db/                        # Database layer
│   ├── models/               # Pydantic models
│   ├── repositories/         # Data access layer (repository pattern)
│   └── services/             # Service layer (caching, business logic)
│       ├── data_service.py   # Includes ML output retrieval (MOCK_DATA)
│       └── cache_service.py  # Redis caching
├── tools/                     # ✨ NEW: LangChain tools for data retrieval
│   ├── customer_tools.py     # Customer data retrieval
│   ├── transaction_tools.py  # Transaction data retrieval
│   ├── alert_tools.py        # Alert data retrieval
│   ├── ml_output_tools.py    # ✨ NEW: ML model output tools (MOCK_DATA)
│   └── registry.py           # Tool registry (17 tools total)
├── evaluation/                # AI agent evaluation framework
│   ├── golden_datasets/       # Ground truth test cases
│   ├── evaluators/            # Specialized quality evaluators
│   ├── conversation/          # Multi-turn conversation tests
│   ├── system/                # System behavior tests
│   ├── scorecard/             # Unified test scorecard
│   ├── test_runner.py         # Main evaluation runner
│   └── results/               # Evaluation results & reports
├── tests/                     # Traditional unit/integration tests
│   └── fixtures/              # Test fixtures and mock data
│       └── ml_model_fixtures.py  # ML output scenarios (MOCK_DATA)
├── docs/                      # Documentation
│   └── PLACEHOLDER_CONTENT_TRACKER.md  # ✨ NEW: Tracks all placeholders
└── notebooks/                # Jupyter notebooks for testing

.claude/                       # Claude Code workspace config
├── agents/                    # Custom Claude agents
│   ├── aml-product-owner.md  # AML domain expert for development
│   └── (other agents)        # Architecture/code review agents
└── commands/                  # Custom slash commands
    ├── check-placeholders.md # ✨ NEW: Find all placeholder content
    └── check-placeholders.sh # Script to inventory placeholders
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

The AML Copilot uses a comprehensive two-suite testing strategy:

#### Suite 1: AML Knowledge Tests (Golden Test Framework)
Tests domain expertise and compliance analysis quality.

**Location**: `evaluation/`
- **Test Runner**: `test_runner.py` - Automated evaluation with specialized evaluators
- **Evaluators**:
  - `correctness_evaluator.py` - Typology identification, red flag detection, citations
  - `completeness_evaluator.py` - Key facts coverage, recommendation quality
  - `hallucination_detector.py` - Invented information detection
- **Golden Datasets**: `evaluation/golden_datasets/` - Ground truth test cases
- **Interactive Notebook**: `notebooks/agent_evaluation_demo.ipynb` - Stakeholder demos

**Quick Start**:
```python
from tests.evaluation.test_runner import run_quick_evaluation

report = run_quick_evaluation()
print(f"Pass Rate: {report.pass_rate:.1%}")
```

**Metrics Tracked**:
- Typology F1 score (precision, recall)
- Red flag detection rate
- Key facts coverage
- Hallucination score
- Overall quality score (0-100)

#### Suite 2: Agent System Tests (In Progress)
Tests AI assistant behavior (conversation, routing, error handling).

**Location**: `evaluation/system/` (documented, not yet implemented)
- Multi-turn conversation tests
- Out-of-topic handling
- Coordinator routing accuracy
- Error handling (missing data, API failures)
- Review loop behavior
- Intent mapping accuracy

**Documentation**:
- **Testing Strategy**: `docs/TESTING_STRATEGY.md` - Comprehensive testing approach
- **Framework Guide**: `evaluation/README.md` - Evaluation framework usage
- **Session Summaries**: `docs/SESSION_SUMMARY_2024_*.md` - Implementation details

**Human Review**: Use `/human-review-test` command for expert validation

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

### Check placeholder content
```bash
# Find all placeholders
/check-placeholders

# Filter by priority
grep -rE "(MOCK_DATA|PLACEHOLDER).*HIGH" --include="*.py" .
```

## Placeholder Content Management (NEW)

### Overview
The codebase contains two types of placeholder content:

1. **MOCK_DATA**: Synthetic/fake data that will be completely replaced
   - ML model outputs (test fixtures)
   - Generated customer/transaction data
   - Placeholder API responses

2. **PLACEHOLDER**: Real content that needs expert review/validation
   - AML domain knowledge (red flags, typologies)
   - Regulatory references
   - Business rules and thresholds

### Code Markers
All placeholder content is clearly marked:
```python
# MOCK_DATA: Brief description - Priority: HIGH/MEDIUM/LOW
# PLACEHOLDER: Brief description - Needs [expert] review - Priority: HIGH/MEDIUM/LOW
```

### Finding Placeholders
Use the `/check-placeholders` slash command or:
```bash
# All placeholders
grep -rE "(MOCK_DATA|PLACEHOLDER)" --include="*.py" .

# High priority only
grep -rE "(MOCK_DATA|PLACEHOLDER).*HIGH" --include="*.py" .

# Items needing expert review
grep -r "Needs.*review" --include="*.py" .
```

### Current Inventory (Summary)
- **19 total markers**: 11 MOCK_DATA + 8 PLACEHOLDER
- **13 HIGH priority**: Must address before production
  - 6 PLACEHOLDER: Red flags, typologies, regulations (need expert review)
  - 5 MOCK_DATA: ML outputs (need service integration)
  - 2 MOCK_DATA: Data generation and retrieval
- **6 MEDIUM priority**: Important for full functionality

### Pre-Production Requirements

**For MOCK_DATA (ML Outputs)**:
1. Integrate ML model service API
2. Connect to feature store
3. Implement real-time/near-real-time predictions
4. Add fallback handling for service failures

**For PLACEHOLDER (Domain Knowledge)**:
1. **AML Compliance Expert Review**:
   - Red flag catalog validation
   - Typology library review
   - Institution-specific customization

2. **Legal/Regulatory Review**:
   - Verify all regulatory citations (CFR sections)
   - Confirm dollar thresholds are current
   - Validate filing deadlines

3. **Security Review**:
   - ML service authentication/authorization
   - Data access patterns
   - PII handling

### Documentation
See `docs/PLACEHOLDER_CONTENT_TRACKER.md` for:
- Complete inventory with file locations
- Replacement strategies
- Expert review checklists
- Production deployment checklist
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

---

## Active Development Tasks (Task 1: Infrastructure)

**Status**: Not started
**Current Todo**: Create middleware framework

### Task 1 Checklist (13 items)

**Middleware Framework** (6 items):
- [ ] Create `middleware/base.py`
- [ ] Create `middleware/logging_middleware.py`
- [ ] Create `middleware/cost_tracking_middleware.py`
- [ ] Create `middleware/aml_compliance_middleware.py`
- [ ] Create `middleware/registry.py`
- [ ] Create `middleware/__init__.py`

**Configuration** (2 items):
- [ ] Update `config/settings.py` with LangSmith settings
- [ ] Create `langgraph.json` for Agent UI

**Testing & Validation** (5 items):
- [ ] Create `tests/infrastructure/test_mock_agent.py` - Mock agent for testing
- [ ] Test LangSmith tracing with mock agent (verify traces appear in LangSmith UI)
- [ ] Test Agent UI with `langgraph dev` (verify graph visualization works)
- [ ] Test middleware framework with mock agent (verify logging, cost tracking)
- [ ] Verify cost tracking logs token usage correctly

### Quick Commands to Resume

```bash
# Check where you are
cat IMPLEMENTATION_PLAN.md

# View full plan
cat /Users/souley/.claude/plans/fizzy-stargazing-kitten.md

# Check todos
# (use Claude's /usage to see current todos)

# Start implementation
# Begin with: Create middleware/base.py
```

### Success Criteria for Task 1

- ✅ Middleware executes for any agent call
- ✅ LangSmith traces appear automatically in UI
- ✅ `langgraph dev` starts successfully
- ✅ Cost tracking logs token usage
- ✅ Mock agent works end-to-end with all infrastructure

**Next**: After Task 1 complete, consult LangChain expert for Task 2 (agents-as-tools implementation)
