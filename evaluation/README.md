# AML Copilot Evaluation Framework

A comprehensive, unified testing and evaluation system for the AML Copilot multi-agent system.

## Overview

This framework provides a **single, modular system** for testing all aspects of the AML Copilot:

- **Unified Test Runner**: Single entry point for Golden, Conversation, and System tests
- **Configurable Weighting**: YAML-based configuration for evaluation weights and thresholds
- **Specialized Evaluators**: Correctness, completeness, and hallucination detection
- **Strategy Pattern**: Pluggable executors and evaluators
- **Type-Safe**: Pydantic models throughout for validation and IDE support
- **Two-Level Scoring**: Test type weights + evaluator weights for final scorecard aggregation

## Architecture

### Core Components

```
evaluation/
├── core/                           # Unified evaluation framework
│   ├── models.py                   # Pydantic models (test cases & results)
│   ├── runner.py                   # UnifiedTestRunner (main entry point)
│   ├── config/                     # Configuration system
│   │   ├── models.py               # Config models (EvaluationConfig)
│   │   └── loader.py               # YAML loaders
│   ├── executors/                  # Test executors (strategy pattern)
│   │   ├── base.py                 # BaseTestExecutor
│   │   ├── golden.py               # GoldenTestExecutor
│   │   ├── conversation.py         # ConversationTestExecutor
│   │   └── system.py               # SystemTestExecutor
│   └── evaluators/                 # Quality evaluators
│       ├── registry.py             # EvaluatorRegistry
│       ├── correctness_evaluator.py
│       ├── completeness_evaluator.py
│       └── hallucination_detector.py
├── config/                         # YAML configurations
│   ├── default_evaluation_config.yaml  # Main config (weights, thresholds)
│   └── evaluators/                 # Evaluator-specific configs
│       ├── correctness_config.yaml
│       ├── completeness_config.yaml
│       └── hallucination_config.yaml
├── golden_datasets/                # Ground truth test cases
├── conversation/                   # Multi-turn test fixtures
└── system/                         # Boundary/error test fixtures
```

## Quick Start

### 1. Run Unified Test Suite

```python
from pathlib import Path
from evaluation.core.runner import UnifiedTestRunner

# Create runner (uses default config)
runner = UnifiedTestRunner()

# Run test suite
report = runner.run_test_suite(
    dataset_path=Path("evaluation/golden_datasets/structuring_cases.json")
)

print(f"Pass Rate: {report.pass_rate:.1%}")
print(f"Overall Score: {report.metrics['avg_overall_score']:.1f}/100")

# View per-category results
for category, stats in report.results_by_category.items():
    print(f"{category}: {stats.passed}/{stats.total} ({stats.pass_rate:.1%})")
```

### 2. Custom Configuration

```python
from evaluation.core.config.models import EvaluationConfig

# Load custom config (adjust weights, thresholds)
config = EvaluationConfig.from_yaml(Path("custom_config.yaml"))

# Create runner with custom config
runner = UnifiedTestRunner(evaluation_config=config)

# Run tests
report = runner.run_test_suite(dataset_path)
```

### 3. Run Specific Test Types

```python
# Auto-detection from JSON structure
runner.run_test_suite(Path("golden_datasets/structuring_cases.json"))  # Golden tests
runner.run_test_suite(Path("conversation/reference_resolution.json"))   # Conversation tests
runner.run_test_suite(Path("system/off_topic_tests.json"))             # System tests

# Or specify explicitly
runner.run_test_suite(dataset_path, test_type="golden")
```

## Test Types

### 1. Golden Tests (AML Business Knowledge)

**Purpose**: Evaluate AML domain expertise, typology identification, regulatory knowledge

**Evaluators**:
- **Correctness** (40%): Typology F1 score, red flag detection, citations
- **Completeness** (40%): Key facts coverage, recommendation quality
- **Hallucination** (20%): Invented information detection

**Example**:
```json
{
  "test_id": "STRUCT_001",
  "test_type": "golden",
  "category": "structuring",
  "priority": "HIGH",
  "description": "Classic structuring - 6 transactions below $10k",
  "input": {
    "user_query": "Analyze recent activity for customer C000123",
    "context": {"cif_no": "C000123"},
    "ml_output": {
      "most_likely_typology": "structuring",
      "feature_values": {"txn_count_near_threshold": 6}
    }
  },
  "expected_output": {
    "typologies_identified": ["structuring"],
    "red_flags_identified": ["transactions_below_threshold"],
    "risk_assessment": "HIGH"
  }
}
```

### 2. Conversation Tests (Multi-Turn Interactions)

**Purpose**: Test message history, reference resolution, cross-turn synthesis

**Validation**: Turn-based validation (no evaluators)

**Example**:
```json
{
  "test_id": "CONV_REF_001",
  "test_type": "conversation",
  "category": "reference_resolution",
  "turns": [
    {
      "turn_number": 1,
      "user_query": "Show me transactions for customer C000001",
      "expected_behavior": "Retrieve and display transactions"
    },
    {
      "turn_number": 2,
      "user_query": "What is their risk rating?",
      "expected_behavior": "Resolve 'their' to C000001"
    }
  ]
}
```

### 3. System Tests (Boundary & Error Handling)

**Purpose**: Test off-topic detection, missing data handling, graceful degradation

**Validation**: Simple pass/fail rules (no evaluators)

**Example**:
```json
{
  "test_id": "SYS_OFF_001",
  "test_type": "system",
  "category": "off_topic",
  "input": {
    "user_query": "What's the weather like?"
  },
  "expected_output": {
    "should_decline": true,
    "should_explain": true
  }
}
```

## Configuration System

### Two-Level Weighting

The framework uses **two levels of weights** for final score calculation:

#### Level 1: Test Type Weights (for final scorecard)
```yaml
# evaluation/config/default_evaluation_config.yaml
test_types:
  golden:
    weight: 0.60      # 60% of final score
  conversation:
    weight: 0.30      # 30% of final score
  system:
    weight: 0.10      # 10% of final score
# Must sum to 1.0 ✓
```

#### Level 2: Evaluator Weights (within test types)
```yaml
golden:
  evaluators:
    - name: correctness
      weight: 0.40    # 40% of golden test score
      threshold: 0.70 # Must score >= 70% to pass
    - name: completeness
      weight: 0.40    # 40% of golden test score
      threshold: 0.75
    - name: hallucination
      weight: 0.20    # 20% of golden test score
      threshold: 0.80
  # Must sum to 1.0 ✓
```

### Final Score Calculation

```python
# Example scores:
golden_score = 85.0       # (correctness * 0.4) + (completeness * 0.4) + (hallucination * 0.2)
conversation_score = 92.0
system_score = 100.0

# Final aggregated score:
final_score = (85 * 0.6) + (92 * 0.3) + (100 * 0.1)
            = 51.0 + 27.6 + 10.0
            = 88.6
```

### Config Auto-Loading

Users can specify evaluator config via **path** or **inline**:

```yaml
# Style 1: Reference external config file
- name: correctness
  weight: 0.40
  threshold: 0.70
  config_path: evaluation/config/evaluators/correctness_config.yaml

# Style 2: Inline config
- name: completeness
  weight: 0.40
  threshold: 0.75
  config:
    key_facts_weight: 0.50
    recommendations_weight: 0.30
```

**Auto-loading**: Pydantic validator automatically loads `config_path` into `config` field, so downstream code only checks `eval_config.config`.

## Evaluators

### Correctness Evaluator

**Evaluates**: Typology identification, red flag detection, risk assessment, regulatory citations

**Configuration**:
```yaml
# evaluation/config/evaluators/correctness_config.yaml
typologies:
  weight_in_correctness: 0.40  # 40% of correctness score
  require_exact_match: false
  allow_additional: true

red_flags:
  weight_in_correctness: 0.30  # 30% of correctness score
  min_detection_rate: 0.70

risk_assessment:
  weight_in_correctness: 0.20  # 20% of correctness score

citations:
  weight_in_correctness: 0.10  # 10% of correctness score
```

**Usage**:
```python
from evaluation.core.evaluators import CorrectnessEvaluator

evaluator = CorrectnessEvaluator()
result = evaluator.evaluate(
    agent_output=agent_output,
    expected_output=test_case.expected_output,
    criteria=test_case.evaluation_criteria
)

print(f"Correctness Score: {result['score']:.2f}")
print(f"Typology F1: {result['typology_score']['f1']:.2f}")
```

### Completeness Evaluator

**Evaluates**: Key facts coverage, recommendation quality, analysis depth

**Configuration**:
```yaml
# evaluation/config/evaluators/completeness_config.yaml
key_facts:
  weight_in_completeness: 0.50  # 50% of completeness score
  min_coverage_rate: 0.75

recommendations:
  weight_in_completeness: 0.30  # 30% of completeness score
  require_specific: true

analysis_depth:
  weight_in_completeness: 0.20  # 20% of completeness score
  check_reasoning: true
```

### Hallucination Detector

**Detects**: Invented customer data, fabricated regulations, invalid typologies

**Configuration**:
```yaml
# evaluation/config/evaluators/hallucination_config.yaml
data_hallucination:
  weight_in_hallucination: 0.40  # 40% of hallucination score
  check_customer_info: true
  strict_mode: true

regulation_hallucination:
  weight_in_hallucination: 0.30  # 30% of hallucination score
  verify_cfr_sections: true

typology_hallucination:
  weight_in_hallucination: 0.20  # 20% of hallucination score

context_hallucination:
  weight_in_hallucination: 0.10  # 10% of hallucination score
```

## Advanced Usage

### Filtering Tests

```python
# Filter by priority
report = runner.run_test_suite(
    dataset_path,
    filters={"priority": "HIGH"}
)

# Filter by category
report = runner.run_test_suite(
    dataset_path,
    filters={"category": "structuring"}
)

# Filter by test IDs
report = runner.run_test_suite(
    dataset_path,
    filters={"test_ids": ["STRUCT_001", "STRUCT_002"]}
)
```

### Custom Evaluators

```python
from evaluation.core.evaluators import EvaluatorRegistry

# Register custom evaluator
registry = EvaluatorRegistry()
registry.register("custom", MyCustomEvaluator())

# Use in runner
runner = UnifiedTestRunner(evaluator_registry=registry)
```

### Accessing Individual Results

```python
report = runner.run_test_suite(dataset_path)

# Iterate through results
for result in report.test_results:
    if result.status == "FAIL":
        print(f"Failed: {result.test_id}")
        if hasattr(result, "correctness_score"):
            print(f"  Correctness: {result.correctness_score:.2f}")
            print(f"  Completeness: {result.completeness_score:.2f}")
```

### Programmatic Config Creation

```python
from evaluation.core.config.models import (
    EvaluationConfig,
    TestTypeEvaluationConfig,
    EvaluatorConfig,
    EvaluatorType
)

# Create custom config programmatically
config = EvaluationConfig(
    version="1.0",
    test_types={
        "golden": TestTypeEvaluationConfig(
            test_type="golden",
            name="Golden Tests",
            description="AML business knowledge",
            weight=0.70,  # Custom weight (70%)
            evaluators=[
                EvaluatorConfig(
                    name=EvaluatorType.CORRECTNESS,
                    weight=0.50,
                    threshold=0.80,
                    config={"typologies": {"weight": 0.5}}
                )
            ]
        )
    }
)

runner = UnifiedTestRunner(evaluation_config=config)
```

## Smoke Testing

Verify the framework is working:

```bash
# Test configuration system
poetry run python evaluation/core/test_config.py

# Test unified runner (requires full environment)
poetry run python evaluation/core/smoke_test.py
```

**Expected Output**:
```
======================================================================
PHASE 2: CONFIGURATION SYSTEM TEST
======================================================================
✅ Config models imported successfully
✅ Default config loaded: 3 test types
✅ Test type weights sum to 1.0 (1.000)
✅ golden: evaluator weights sum to 1.0 (1.000)
✅ Config auto-loading from paths (3 evaluator configs)
✅ Final score calculated correctly: 88.6
✅ Evaluator registry initialized: 3 evaluators
```

## Metrics & Reporting

### Test Result Status

- **PASS**: All criteria met, scores above thresholds
- **FAIL**: One or more scores below threshold
- **ERROR**: Execution error (exception during test)

### Report Structure

```python
class UnifiedEvaluationReport(BaseModel):
    report_id: str
    run_date: datetime
    test_type: str                           # "golden", "conversation", "system"
    total_cases: int
    passed: int
    failed: int
    errors: int
    pass_rate: float                          # 0-1
    metrics: Dict[str, float]                 # Test-type-specific metrics
    results_by_category: Dict[str, CategoryStats]
    test_results: List[BaseTestResult]        # Individual results
    execution_time_seconds: float
```

### Scorecard Integration

The framework generates unified reports that can be consumed by the scorecard:

```python
# Generate final scorecard across all test types
test_type_scores = {
    "golden": golden_report.metrics["avg_overall_score"],
    "conversation": conversation_report.pass_rate * 100,
    "system": system_report.pass_rate * 100
}

final_score = config.calculate_final_score(test_type_scores)
print(f"Final Scorecard Score: {final_score:.1f}/100")
```

## Design Patterns

### Strategy Pattern (Evaluators)

Evaluators are injected at runtime, not stored in executors:

```python
# UnifiedTestRunner orchestrates:
for eval_config in test_config.evaluators:
    evaluator = registry.get_evaluator(eval_config.name)

    # Strategy pattern: inject evaluator + config
    eval_result = executor.evaluate(
        evaluator=evaluator,
        evaluator_config=eval_config.config,  # Auto-loaded from YAML
        test_case=test_case,
        agent_output=agent_output
    )
```

**Benefits**:
- Executors are stateless (no config burden)
- Evaluators are reusable across test types
- Configuration is centralized in YAML

### Registry Pattern (Test Types)

Test types are registered with executors:

```python
class TestRegistry(BaseModel):
    test_types: Dict[str, TestTypeConfig]

# Maps test type → executor class → test case class → result class
# Enables dynamic loading and extensibility
```

### Pydantic Validation

All models use Pydantic for:
- Type validation
- Required field checking
- Custom validators (weights sum to 1.0)
- Automatic JSON serialization

## Best Practices

### 1. Version Your Configs

```
evaluation/config/
├── v1.0/
│   └── evaluation_config.yaml
├── v1.1/
│   └── evaluation_config.yaml
└── default_evaluation_config.yaml  # Current version
```

### 2. Test Configuration Changes

```python
# Before changing weights in production:
config = EvaluationConfig.from_yaml(Path("proposed_config.yaml"))

# Run tests with new config
runner = UnifiedTestRunner(evaluation_config=config)
report = runner.run_test_suite(dataset_path)

# Compare to baseline
if report.pass_rate < baseline_pass_rate:
    print("⚠️ New config reduces pass rate")
```

### 3. Monitor Weight Impact

Track how weight changes affect scores:

```python
# Experiment with weights
configs = [
    {"golden": 0.60, "conversation": 0.30, "system": 0.10},
    {"golden": 0.50, "conversation": 0.40, "system": 0.10},
    {"golden": 0.70, "conversation": 0.20, "system": 0.10},
]

for weights in configs:
    # Create config, run tests, compare
    ...
```

### 4. Keep Test Cases Independent

- Each test should run standalone
- Don't rely on execution order
- Use fresh state for each test

### 5. Regular Expert Review

- **Monthly**: Review 10% sample of golden tests
- **Before release**: Review all HIGH priority tests
- **After prompt changes**: Targeted review of affected categories

## Troubleshooting

### Config Validation Errors

```python
# Common error: Weights don't sum to 1.0
ValidationError: Evaluator weights must sum to 1.0, got 0.95

# Fix: Adjust weights in YAML
evaluators:
  - name: correctness
    weight: 0.40
  - name: completeness
    weight: 0.40
  - name: hallucination
    weight: 0.20  # Sum = 1.0 ✓
```

### Low Scores

1. **Low Correctness**: Check ML model outputs, prompt engineering
2. **Low Completeness**: Verify data retrieval, check for missing facts
3. **Hallucinations**: Review source data completeness, check temperature

### Missing Evaluator Configs

```python
# If config_path references non-existent file:
# Evaluator will use empty config {}
# Check evaluator can handle missing config gracefully
```

## Migration from Legacy System

The unified framework replaces 3 separate runners:

**Old**:
```python
# evaluation/test_runner.py (golden tests only)
# evaluation/conversation/test_conversations.py
# evaluation/system/run_system_tests.py
```

**New**:
```python
from evaluation.core.runner import UnifiedTestRunner

runner = UnifiedTestRunner()
runner.run_test_suite(dataset_path)  # Handles all test types
```

**Legacy wrappers** are available for backward compatibility but deprecated.

## References

- **Framework Design**: `/Users/souley/.claude/plans/modular-questing-hare.md`
- **Testing Strategy**: `docs/TESTING_STRATEGY.md`
- **Test Types Overview**: `evaluation/TEST_TYPES_OVERVIEW.md`
- **Placeholder Tracker**: `docs/PLACEHOLDER_CONTENT_TRACKER.md`

## Support

For questions or issues:
1. Check configuration examples in `evaluation/config/`
2. Review test case examples in `evaluation/golden_datasets/`
3. Run smoke tests to verify setup
4. Consult design plan in `.claude/plans/`
