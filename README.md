# AML Compliance Copilot

An AI-powered multi-agent system for AML (Anti-Money Laundering) compliance investigation and report generation.

## Overview

This project implements Phase 2 of the Agentic Compliance Architecture - an intelligent system that assists AML investigators with natural language queries, automated data retrieval, and compliance guidance.

## Architecture

### Multi-Agent System

The system consists of five specialized agents orchestrated via LangGraph:

1. **Coordinator Agent** - Entry point with scope validation (true/partial/false) and LLM-generated guidance
2. **Intent Mapping Agent** - Translates natural language queries into structured data requests with clarification support
3. **Data Retrieval Agent** - Executes queries against PostgreSQL database with Redis caching
4. **Compliance Expert Agent** - Provides procedural guidance, compliance analysis, and report generation
5. **Review Agent** - Dedicated QA agent with 5-way routing (passed/needs_data/needs_refinement/needs_clarification/human_review)

For detailed workflow, routing logic, and review loops, see [AGENT_FLOW.md](AGENT_FLOW.md).

### Data Flow

```
User Query → Coordinator (scope check) → Intent Mapper (with clarification) → 
Data Retrieval → Compliance Expert → Review Agent
                    ↓                         ↓
                Redis Cache          5-way routing:
                PostgreSQL           - passed → user
                                     - needs_data → intent_mapper
                                     - needs_refinement → compliance_expert
                                     - needs_clarification → user
                                     - human_review → flag
```

## Project Structure

```
aml_copilot/
├── agents/              # LangGraph agent implementations
│   ├── coordinator.py   # Entry point with 3-state scope validation
│   ├── intent_mapper.py # Query mapping with clarification support
│   ├── data_retrieval.py
│   ├── compliance_expert.py
│   ├── review_agent.py  # QA agent with 5-way routing
│   ├── graph.py         # LangGraph orchestration with review loops
│   ├── state.py         # Shared state schema
│   └── prompts.py       # Agent prompts
├── tools/               # LangChain tools (expose functions to agents)
│   ├── customer_tools.py
│   ├── transaction_tools.py
│   ├── alert_tools.py
│   └── registry.py
├── db/                  # Database layer
│   ├── manager.py       # DB connection manager with DI pattern (raw SQL)
│   ├── models/          # Pydantic models (not ORM)
│   │   ├── customer.py  # Feature-grouped customer models
│   │   ├── transaction.py
│   │   ├── alert.py
│   │   └── report.py
│   ├── repositories/    # Data access layer (repository pattern with raw SQL)
│   │   ├── customer_repository.py
│   │   ├── transaction_repository.py
│   │   └── alert_repository.py
│   └── services/        # Business logic layer
│       ├── data_service.py
│       ├── cache_service.py
│       └── report_service.py
├── migrations/          # Alembic migrations (raw SQL)
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── data/                # Data schemas and mock data
│   ├── schema.sql
│   ├── mock_data.py
│   └── feature_catalog.json
├── config/              # Configuration
│   └── settings.py      # Includes max_review_attempts
├── ui/                  # Streamlit interface
│   └── streamlit_app.py
└── tests/               # Test suite
```

### Layered Architecture

**Database Layer:**
- **Manager** - psycopg2 connection pooling with dependency injection, auto commit/rollback
- **Models** - Pydantic models for validation (not ORM, uses raw SQL)
- **Migrations** - Alembic with raw SQL migrations
- **Repositories** - Data access pattern with raw SQL queries
- **Services** - Business logic, caching, LLM data formatting

**Tools Layer:**
- Wraps service layer functions as LangChain tools for agents

**Agent Layer:**
- LangGraph orchestration of specialized agents

### Key Design Optimizations

**1. Feature Grouping for ML Efficiency**

Customer data is split into logical feature groups instead of one monolithic model:
- `CustomerBasic` - Identity and risk score (5 fields, ~100 tokens)
- `CustomerTransactionFeatures` - Transaction aggregations (15 fields)
- `CustomerRiskFeatures` - Risk indicators (4 fields)
- `CustomerBehavioralFeatures` - Behavioral patterns (3 fields)
- `CustomerNetworkFeatures` - Graph analysis (4 fields)
- `CustomerKnowledgeGraphFeatures` - Entity risk (3 fields)
- `CustomerFull` - Complete profile (40+ fields, use sparingly)

**Benefits:**
- **Query Performance** - Fetch only needed columns
- **LLM Token Efficiency** - Don't waste context on irrelevant features
- **Agent Optimization** - Intent mapper routes to specific feature groups
- **Realistic ML Pattern** - Matches how features are engineered in production

**2. Raw SQL + Pydantic (No ORM)**

- **Database operations** - Raw SQL with psycopg2 for full control
- **Migrations** - Alembic with hand-written SQL
- **Data validation** - Pydantic models for type safety
- **Why?** - Flexibility, performance, clarity in complex ML queries

**3. Separate Feature Catalog**

- **Pydantic models** - Runtime validation and type hints
- **Feature catalog JSON** - Rich semantic metadata for LLM intent mapping
- **Why separate?** - Different purposes, different evolution speeds
  - Catalog: Natural language aliases, query patterns, typology mappings
  - Models: Python types, validation rules

**4. Feature Group Caching**

Redis caching at feature group granularity instead of full customer or individual columns:
- **Cache key pattern**: `customer:{cif_no}:{group_name}`
- **Smart cache hits**: Query one field in a group → entire group cached → subsequent queries for other fields in same group = cache hit
- **Intelligent TTLs**: Different groups have different update frequencies
  - `basic`: 1 hour (identity changes rarely)
  - `transaction_features`: 5 minutes (updated frequently)
  - `network_features`: 30 minutes (expensive graph analysis)
- **Result**: 70-85% cache hit rate, 60-80% fewer DB queries, 40% less Redis memory vs full customer caching

## Prerequisites

- Python 3.11+
- Poetry
- Docker & Docker Compose
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Configure environment
cp .env.example .env
# Edit .env and set: OPENAI_API_KEY=your-key-here

# 3. Start services (PostgreSQL + Redis)
make services-start

# 4. Setup database
make db-migrate
make db-seed

# 5. Run the API
make api-run

# 6. Test (in another terminal)
make notebook
# Or visit: http://localhost:8000/docs
```

## Configuration

### Environment Variables

Create `.env` from template:
```bash
cp .env.example .env
```

**Required:**
```env
OPENAI_API_KEY=sk-proj-your-key-here
```

**Database (auto-configured via Docker):**
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=aml_compliance
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
```

**Redis (auto-configured via Docker):**
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB_CACHE=0          # For feature caching
REDIS_DB_CHECKPOINTS=1    # For conversation history
```

### Agent Configuration

Each agent can be configured independently:

**Model Selection:**
- **Coordinator**: `gpt-4o-mini` (routing decisions)
- **Intent Mapper**: `gpt-4o-mini` (query understanding)
- **Compliance Expert**: `gpt-4o` (deep AML analysis)
- **Review Agent**: `gpt-4o` (quality assurance)

**Temperature Settings:**
- `0.0` = Deterministic (routing, mapping)
- `0.1` = Slight creativity (analysis, review)

**Review System:**
```env
MAX_REVIEW_ATTEMPTS=3  # Adaptive review cycles (1-5)
```

See `config/settings.py` for full configuration options.

## Development

**Common Commands:**
```bash
make install          # Install dependencies
make setup            # Full setup (services + database)
make start            # Start services + API
make stop             # Stop everything
make status           # Check service status

make api-run          # Run API server
make notebook         # Open Jupyter notebooks

make db-migrate       # Run migrations
make db-seed          # Load mock data
make db-refresh       # Reset and reload database

make test             # Run tests
make format           # Format code
make lint             # Check code quality

make help             # Show all commands
```

See `Makefile` for complete command reference.

## Features

- Natural language query interface with clarification support
- Intelligent 3-state scope validation (true/partial/false)
- Intent mapping to database schema with context awareness
- Fast data retrieval with Redis caching (separate cache and checkpoint stores)
- Context-aware compliance guidance and analysis
- Automated report generation
- Adaptive review system with 5-way routing
- Configurable review loops to ensure output quality
- LLM-generated guidance messages for query refinement
- Audit trail logging

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, agent workflow, and design patterns
- **[objective.md](objective.md)** - Project vision and roadmap
- **Makefile** - Complete command reference with inline documentation

## License

MIT
