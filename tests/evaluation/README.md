# AML Copilot Evaluation Framework

A comprehensive testing and evaluation system for the AML Copilot multi-agent system.

## Overview

This framework provides:
- **Golden Test Datasets**: Ground truth test cases with expected outputs
- **Automated Evaluation**: Systematic scoring of agent outputs
- **Specialized Evaluators**: Correctness, completeness, and hallucination detection
- **Regression Testing**: Compare performance across versions
- **Human-in-the-Loop**: Expert review integration

## Quick Start

### 1. Run Evaluation Suite

```python
from pathlib import Path
from tests.evaluation.test_runner import run_quick_evaluation

# Run all structuring test cases
report = run_quick_evaluation(
    dataset_path="tests/fixtures/golden_datasets/structuring_cases.json"
)

print(f"Pass Rate: {report.pass_rate:.1%}")
print(f"Average Score: {report.avg_overall_score:.1f}/100")
```

### 2. Interactive Notebook

For demonstrations and exploration, use the interactive notebook:

```bash
jupyter notebook notebooks/agent_evaluation_demo.ipynb
```

### 3. Test Specific Cases

```python
from tests.evaluation.test_runner import AgentEvaluationRunner
from pathlib import Path

runner = AgentEvaluationRunner()

# Load test cases
cases = runner.load_golden_test_cases(
    Path("tests/fixtures/golden_datasets/structuring_cases.json"),
    priority="HIGH"  # Filter by priority
)

# Run single test
result = runner.execute_test_case(cases[0])
print(f"Status: {result.status}")
print(f"Score: {result.overall_score:.1f}/100")
```

## Directory Structure

```
tests/evaluation/
├── README.md                    # This file
├── test_runner.py              # Main test runner
├── models.py                   # Pydantic models for test cases
├── evaluators/                 # Specialized evaluators
│   ├── __init__.py
│   ├── correctness_evaluator.py      # Typology, red flag accuracy
│   ├── completeness_evaluator.py     # Key facts, recommendations
│   └── hallucination_detector.py     # Invented information detection
└── reports/                    # Generated evaluation reports
```

## Evaluators

### Correctness Evaluator

Evaluates:
- **Typology Identification**: Precision, recall, F1 score
- **Red Flag Detection**: Detection rate
- **Risk Assessment**: Accuracy of risk level
- **Regulatory Citations**: Citation accuracy

```python
from tests.evaluation.evaluators import CorrectnessEvaluator

evaluator = CorrectnessEvaluator()

result = evaluator.evaluate(
    agent_output=agent_output,
    expected_typologies=["structuring"],
    expected_red_flags=["transactions_below_threshold"],
    expected_risk="HIGH",
    expected_citations=["31 USC 5324"],
    allow_additional_typologies=False
)

print(f"Correctness Score: {result['correctness_score']:.2f}")
print(f"Typology F1: {result['typology_score']['f1']:.2f}")
```

### Completeness Evaluator

Evaluates:
- **Key Facts Coverage**: What % of expected facts were mentioned
- **Recommendation Quality**: Actionability and coverage
- **Attribution Chain**: Does the agent explain reasoning?

```python
from tests.evaluation.evaluators import CompletenessEvaluator

evaluator = CompletenessEvaluator()

result = evaluator.evaluate(
    agent_output=agent_output,
    expected_facts=["6 transactions", "$9,850 average", "$10,000 threshold"],
    expected_recommendations=["verify transactions", "review locations"],
    require_attribution_chain=True
)

print(f"Completeness Score: {result['completeness_score']:.2f}")
print(f"Facts Coverage: {result['key_facts']['coverage_percentage']:.1f}%")
```

### Hallucination Detector

Detects:
- **Invented Amounts**: Transaction amounts not in source data
- **Fabricated Dates**: Specific dates not provided
- **Invalid Citations**: Non-existent regulations
- **Prohibited Content**: Things that should not appear

```python
from tests.evaluation.evaluators import HallucinationDetector

detector = HallucinationDetector()

result = detector.evaluate(
    agent_output=agent_output,
    source_data={"ml_output": ml_output, "customer_data": customer_data},
    should_not_include=["FILE_SAR", "CLOSE", "January 15"]
)

print(f"Hallucination Score: {result['hallucination_score']:.2f}")
print(f"Hallucinations Found: {result['hallucination_count']}")
print(f"Is Trustworthy: {result['is_trustworthy']}")
```

## Test Case Format

Golden test cases use this structure:

```json
{
  "test_id": "STRUCT_001",
  "category": "structuring",
  "priority": "HIGH",
  "description": "Classic structuring - 6 transactions just below $10k threshold",

  "input": {
    "user_query": "Analyze the recent activity for customer C000123",
    "context": {
      "cif_no": "C000123",
      "alert_id": "ALT_2024_001"
    },
    "ml_output": {
      "most_likely_typology": "structuring",
      "typology_likelihoods": {"structuring": 0.85},
      "feature_values": {
        "txn_count_near_threshold": 6,
        "avg_txn_amount": 9850.50
      }
    }
  },

  "expected_output": {
    "typologies_identified": ["structuring"],
    "red_flags_identified": ["transactions_below_threshold"],
    "risk_assessment": "HIGH",
    "key_facts_mentioned": [
      "6 transactions",
      "$9,850",
      "$10,000 threshold"
    ],
    "should_not_include": ["FILE_SAR", "CLOSE"]
  },

  "evaluation_criteria": {
    "must_identify_typology": true,
    "must_identify_red_flags": true,
    "must_cite_regulations": true,
    "must_provide_recommendations": true,
    "must_not_hallucinate": true,
    "min_key_facts_coverage": 0.8
  }
}
```

## Evaluation Metrics

### Scoring

Each test receives scores in three dimensions:

1. **Correctness** (0-1): Did agent identify the right patterns?
   - Typology identification (40%)
   - Red flag detection (30%)
   - Risk assessment (20%)
   - Regulatory citations (10%)

2. **Completeness** (0-1): Did agent cover all important details?
   - Key facts coverage (50%)
   - Recommendation quality (40%)
   - Attribution chain (10%)

3. **Hallucination** (0-1): Did agent invent information?
   - No invented amounts (HIGH severity: -0.3)
   - No fabricated dates (MEDIUM severity: -0.15)
   - Valid citations only (MEDIUM severity: -0.15)
   - No prohibited content (HIGH severity: -0.3)

**Overall Score** (0-100):
```
Overall = (Correctness × 40 + Completeness × 40 + Hallucination × 20)
```

### Pass/Fail Criteria

A test case **PASSES** if:
- Correctness score ≥ criteria threshold
- Completeness score ≥ criteria threshold (typically 0.8)
- Hallucination score ≥ 0.8 (trustworthy)
- All "must" criteria are met

## Regression Testing

### Create Baseline

After validating a version works well:

```python
# Run full evaluation
report = runner.run_evaluation_suite(dataset_path)

# Save as baseline
baseline_path = Path("tests/evaluation/baselines/v1.0.0.json")
runner.save_report(report, baseline_path)
```

### Compare to Baseline

```python
# Run new evaluation with baseline comparison
report = runner.run_evaluation_suite(
    dataset_path,
    baseline_path=Path("tests/evaluation/baselines/v1.0.0.json")
)

if report.regressions_detected:
    print("⚠️ Regressions detected:")
    for regression in report.regressions_detected:
        print(f"  - {regression}")
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: AML Agent Evaluation

on: [pull_request]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run Golden Test Suite
        run: |
          python -c "
          from tests.evaluation.test_runner import run_quick_evaluation
          report = run_quick_evaluation()

          # Quality gates
          if report.pass_rate < 0.95:
              print(f'❌ Pass rate {report.pass_rate:.1%} below 95% threshold')
              exit(1)

          if report.avg_overall_score < 85:
              print(f'❌ Avg score {report.avg_overall_score:.1f} below 85 threshold')
              exit(1)

          print(f'✅ Tests passed! Pass rate: {report.pass_rate:.1%}, Avg score: {report.avg_overall_score:.1f}')
          "

      - name: Check for Regressions
        run: |
          python tests/evaluation/check_regressions.py \
            --baseline baselines/main.json \
            --current tests/evaluation/reports/latest.json
```

## Adding New Test Cases

### 1. Create Test Case JSON

```json
{
  "test_id": "LAYER_001",
  "category": "layering",
  "priority": "HIGH",
  "description": "Rapid fund movement across accounts",
  "input": { ... },
  "expected_output": { ... },
  "evaluation_criteria": { ... }
}
```

### 2. Validate with AML Expert

Have an AML compliance expert review:
- Is the scenario realistic?
- Are expected outputs correct?
- Are evaluation criteria appropriate?

### 3. Add to Golden Dataset

```bash
# Add to appropriate category file
tests/fixtures/golden_datasets/layering_cases.json
```

### 4. Run Test

```python
report = run_quick_evaluation(
    dataset_path="tests/fixtures/golden_datasets/layering_cases.json",
    priority="HIGH"
)
```

## Human Review Process

For expert validation, use the human review command:

```bash
# In Claude Code CLI
/human-review-test category=structuring
```

This presents outputs in a review-friendly format with scoring rubrics:
- Technical Accuracy (0-10)
- Practical Usefulness (0-10)
- Regulatory Compliance (0-10)
- Overall Quality (0-10)

## Best Practices

### 1. Test Boundary Conditions
- Clear cases (obvious structuring)
- Borderline cases (ambiguous patterns)
- Negative cases (normal activity)
- Missing data scenarios

### 2. Keep Tests Independent
- Each test should run independently
- Don't rely on previous test results
- Use fresh state for each test

### 3. Version Your Datasets
```
golden_datasets/
├── v1.0/
│   └── structuring_cases.json
├── v1.1/
│   └── structuring_cases.json  # Updated with new cases
└── current/
    └── structuring_cases.json  # Symlink to latest
```

### 4. Regular Expert Review
- Monthly: Review 10% sample
- Before release: Review high-priority cases
- After prompt changes: Targeted review

### 5. Monitor Metrics Trends
Track over time:
- Pass rate by category
- Average scores by dimension
- Hallucination rate
- Regression frequency

## Troubleshooting

### Test Execution Errors

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

runner = AgentEvaluationRunner()
result = runner.execute_test_case(test_case)
```

### Low Scores

1. **Low Correctness**: Agent not identifying patterns
   - Check prompt engineering
   - Review ML model outputs
   - Validate agent routing

2. **Low Completeness**: Missing key facts
   - Are facts in source data?
   - Is agent reading all relevant data?
   - Review data retrieval logic

3. **Hallucinations Detected**: Agent inventing information
   - Check source data completeness
   - Review prompt instructions
   - Look for temperature/sampling issues

## References

- **Framework Documentation**: `docs/AGENT_TESTING_FRAMEWORK.md`
- **Testing Strategy**: `docs/TESTING_STRATEGY.md`
- **Session Summary**: `docs/SESSION_SUMMARY_2024_01.md`
- **Placeholder Tracker**: `docs/PLACEHOLDER_CONTENT_TRACKER.md`

## Support

For questions or issues with the evaluation framework:
1. Check documentation in `docs/`
2. Review test case examples in `tests/fixtures/golden_datasets/`
3. Examine interactive notebook: `notebooks/agent_evaluation_demo.ipynb`
