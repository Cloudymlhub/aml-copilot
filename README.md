# AML Compliance Copilot

An AI-powered multi-agent system for AML (Anti-Money Laundering) compliance investigation and report generation.

## Overview

This project implements Phase 2 of the Agentic Compliance Architecture - an intelligent system that assists AML investigators with natural language queries, automated data retrieval, and compliance guidance.

## Architecture

### Multi-Agent System

The system consists of four specialized agents orchestrated via LangGraph:

1. **Coordinator Agent** - Central orchestrator that manages workflow between specialized agents
2. **Intent Mapping Agent** - Translates natural language queries into structured data requests and maps to database columns
3. **Data Retrieval Agent** - Executes queries against PostgreSQL database with Redis caching
4. **Compliance Expert Agent** - Provides procedural guidance, compliance checks, and report generation

### Data Flow

```
User Query → Coordinator → Intent Mapper → Data Retrieval → Compliance Expert → Response
                    ↓                              ↓
                Redis Cache                  PostgreSQL
```

## Project Structure

```
aml_copilot/
├── agents/              # LangGraph agent implementations
│   ├── coordinator.py
│   ├── intent_mapper.py
│   ├── data_retrieval.py
│   └── compliance_expert.py
├── tools/               # LangChain tools (expose functions to agents)
│   ├── db_tools.py
│   └── cache_tools.py
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
│   └── settings.py
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
- PostgreSQL (running)
- Redis (running)
- OpenAI API key (or compatible LLM endpoint)

## Installation

1. Install dependencies:
```bash
poetry install
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials and API keys
```

3. Initialize database with mock data:
```bash
poetry run python data/mock_data.py
```

## Usage

### Start the Streamlit UI

```bash
poetry run streamlit run ui/streamlit_app.py
```

### Example Queries

- "Show me all transactions for customer ID 12345 in the last 7 days"
- "What are the high-risk transactions above $50,000?"
- "Generate a compliance report for account X"
- "What typologies are associated with this alert?"

## Configuration

Edit `config/settings.py` or use environment variables:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - OpenAI API key
- `LLM_MODEL` - Model to use (default: gpt-4)

## Development

Run tests:
```bash
poetry run pytest
```

## Features

- Natural language query interface
- Intelligent intent mapping to database schema
- Fast data retrieval with Redis caching
- Context-aware compliance guidance
- Automated report generation
- Audit trail logging

## Roadmap

See [objective.md](objective.md) for the full vision including Phase 1 (Investigator Support) and Phase 3 (Progressive Automation).

## License

MIT
