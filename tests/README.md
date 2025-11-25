# Unit Tests

This directory contains traditional unit and integration tests for the AML Copilot codebase.

> **Note**: For AI agent evaluation (conversation tests, AML knowledge tests, system behavior tests), see **[evaluation/](../evaluation/README.md)**

## What's Tested Here

- **Repository Layer**: Database access patterns, SQL queries
- **Service Layer**: Business logic, caching, data formatting
- **API Endpoints**: FastAPI route handlers, request/response validation
- **Tool Integration**: LangChain tool implementations
- **Utilities**: Helper functions, data transformations

## Running Tests

### Run all unit tests:
```bash
make test-unit
```

### Run with coverage:
```bash
make test-coverage
```

### Run specific test file:
```bash
PYTHONPATH=$(pwd) poetry run python -m pytest tests/test_repositories.py -v
```

## Test Structure

```
tests/
├── README.md                    # This file
├── test_repositories.py         # Repository layer tests
├── test_services.py             # Service layer tests
├── test_api.py                  # API endpoint tests
├── test_tools.py                # Tool integration tests
├── config.py                    # Test configuration (deprecated)
└── fixtures/                    # Test fixtures and mock data
    └── ml_model_fixtures.py     # ML model mock data
```

## Writing Tests

Use pytest conventions:

```python
def test_customer_repository_get_by_cif():
    """Test retrieving customer by CIF number."""
    # Arrange
    cif_no = "CIF001"

    # Act
    customer = customer_repo.get_by_cif(cif_no)

    # Assert
    assert customer is not None
    assert customer.cif_no == cif_no
```

## Separation of Concerns

This project separates **unit testing** from **AI agent evaluation**:

### Unit Tests (`tests/`)
- Traditional software testing
- Tests code correctness
- Fast execution
- High coverage targets (80%+)

### Agent Evaluation (`evaluation/`)
- AI quality assessment
- Tests domain expertise
- Slower execution (requires LLM calls)
- Different metrics (F1 scores, hallucination detection)

See **[evaluation/README.md](../evaluation/README.md)** for AI agent testing.

## Tools

- **pytest**: Test runner
- **pytest-cov**: Coverage reporting
- **fixtures**: Located in `tests/fixtures/`

## CI/CD Integration

Unit tests run automatically on:
- Pre-commit hooks (optional)
- Pull requests
- Main branch merges

**Target coverage**: 80% for core business logic

## Adding Tests

1. Create test file matching the module: `test_<module>.py`
2. Use descriptive test names: `test_<function>_<scenario>()`
3. Follow AAA pattern: Arrange, Act, Assert
4. Use fixtures for common setup
5. Mock external dependencies (database, API calls, LLMs)

## Current Status

- Framework: ✅ Complete (pytest + pytest-cov)
- Coverage: ⚠️ Partial (needs expansion)
- Priority: Add tests for repositories, services, and tools

## Related Documentation

- **[evaluation/README.md](../evaluation/README.md)** - AI agent evaluation framework
- **[docs/TESTING_STRATEGY.md](../docs/TESTING_STRATEGY.md)** - Overall testing approach
- **[Makefile](../Makefile)** - Test commands reference
