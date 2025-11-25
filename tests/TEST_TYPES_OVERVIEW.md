# AML Copilot - Test Types Overview

A comprehensive guide to understanding all test types, their purposes, and outputs.

---

## 🎯 Three Test Types

The AML Copilot has **three distinct test suites**, each with different purposes and outputs:

### 1. **Conversation Tests** (NEW!)
**Purpose**: Validate multi-turn conversation behavior and data access patterns

**Location**: `tests/system/test_conversations.py`

**What it tests**:
- Multi-turn conversation flow
- Reference resolution ("their", "that customer")
- Cross-turn data synthesis (using message history)
- Context accumulation across turns
- Critical architectural question: "Is message history sufficient?"

**Output Format**: **JSON files**
- Timestamped: `tests/results/conversation_tests_20251125_173715.json`
- Latest: `tests/results/conversation_tests_latest.json`

**Run with**:
```bash
make test-conversations
# or
python tests/system/test_conversations.py
```

**Output Structure**:
```json
{
  "timestamp": "2025-11-25T17:37:15...",
  "total": 13,
  "passed": 10,
  "failed": 3,
  "errors": 0,
  "pass_rate": 0.769,
  "category_stats": {
    "reference_resolution": {"total": 5, "passed": 4, "failed": 1},
    "cross_turn_data_access": {"total": 5, "passed": 4, "failed": 1},
    "context_accumulation": {"total": 3, "passed": 2, "failed": 1}
  },
  "results": [
    {
      "test_id": "CONV_REF_001",
      "category": "reference_resolution",
      "status": "PASS",
      "turn_results": [...],
      "error_message": null
    }
  ]
}
```

**View results**:
```bash
make test-results
# or
cat tests/results/conversation_tests_latest.json | jq '.category_stats'
```

---

### 2. **Evaluation Tests** (AML Knowledge)
**Purpose**: Validate AML domain expertise and compliance analysis quality

**Location**: `tests/evaluation/test_runner.py`

**What it tests**:
- Typology identification (precision, recall, F1)
- Red flag detection
- Risk assessment accuracy
- Regulatory citations
- Key facts coverage
- Hallucination detection

**Output Format**: **Python objects** (can be saved to JSON)
- Returns `EvaluationReport` object
- Can save to JSON with `runner.save_report(report, path)`

**Run with**:
```bash
make test-evaluation
# or
python -c "from tests.evaluation.test_runner import run_quick_evaluation; run_quick_evaluation()"
```

**Output Structure** (Python object):
```python
EvaluationReport(
    total_cases=3,
    passed=2,
    failed=1,
    pass_rate=0.667,
    avg_overall_score=78.5,
    results=[
        TestResult(
            test_id="STRUCT_001",
            status="PASS",
            overall_score=85.2,
            correctness_score=0.90,
            completeness_score=0.85,
            hallucination_score=1.0
        )
    ]
)
```

**Interactive demo**:
```bash
jupyter notebook notebooks/agent_evaluation_demo.ipynb
```

---

### 3. **System Tests** (Basic Behavior)
**Purpose**: Validate basic AI assistant capabilities

**Location**: `tests/system/run_system_tests.py`

**What it tests**:
- Off-topic handling (boundary tests)
- Error handling (missing data, invalid inputs)
- Basic routing decisions

**Output Format**: **Console output only** (pass/fail)
- No persistent JSON reports
- Simple test runner with print statements

**Run with**:
```bash
python tests/system/run_system_tests.py
```

**Output Example**:
```
=== AML COPILOT SYSTEM TESTS ===

Running boundary tests...
✅ BOUNDARY_001 PASSED
✅ BOUNDARY_002 PASSED
❌ BOUNDARY_003 FAILED

Results: 2/3 passed (66.7%)
```

---

## 📊 Comparison Table

| Feature | Conversation Tests | Evaluation Tests | System Tests |
|---------|-------------------|------------------|--------------|
| **Purpose** | Multi-turn behavior | AML knowledge | Basic behavior |
| **Output** | JSON files | Python objects | Console only |
| **Persistence** | Always saved | Optional | None |
| **Metrics** | Pass/Fail | Scores (0-100) | Pass/Fail |
| **Fixtures** | `conversation_cases.json` | `golden_datasets/*.json` | `*_cases.json` |
| **Results Dir** | `tests/results/` | None (manual save) | None |
| **Notebook** | ❌ Not yet | ✅ Yes | ❌ No |
| **Makefile** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Status** | ✅ Complete | ✅ Complete | ⚠️ Basic |

---

## 🚀 Quick Commands

### Run All Tests
```bash
make test  # Runs all three types
```

### Run Individual Test Types
```bash
make test-conversations      # Conversation tests → JSON
make test-evaluation         # AML knowledge → Python object
make test-unit               # System tests → Console
```

### View Results
```bash
make test-results            # View latest conversation results
make test-results-history    # Show all conversation test runs
```

### Run Specific Categories
```bash
# Only cross-turn data access tests
make test-conversations-category CATEGORY=cross_turn_data_access

# Only reference resolution tests
make test-conversations-category CATEGORY=reference_resolution
```

---

## 📁 Where Results Are Stored

### Conversation Tests
- **Always saved automatically**
- Location: `tests/results/`
- Files:
  - `conversation_tests_YYYYMMDD_HHMMSS.json` (timestamped, git-ignored)
  - `conversation_tests_latest.json` (committed to git)

### Evaluation Tests
- **NOT saved automatically**
- Must manually save:
  ```python
  from pathlib import Path
  runner = AgentEvaluationRunner()
  report = runner.run_evaluation_suite(dataset_path)
  runner.save_report(report, Path("my_results.json"))
  ```

### System Tests
- **No persistence**
- Console output only
- Must manually capture if needed

---

## 🎓 When to Use Each Test Type

### Use **Conversation Tests** when:
- Testing multi-turn conversation flow
- Validating reference resolution ("their", "that customer")
- Ensuring data synthesis across turns
- Checking if message history is sufficient
- **Example**: "Does Turn 3 correctly reference data from Turn 1?"

### Use **Evaluation Tests** when:
- Testing AML domain knowledge
- Validating typology identification
- Checking regulatory citation accuracy
- Detecting hallucinations
- **Example**: "Does the agent correctly identify structuring with 90% F1?"

### Use **System Tests** when:
- Testing basic boundary handling
- Checking error handling
- Quick smoke tests
- **Example**: "Does the agent decline off-topic questions?"

---

## 📝 Example Workflows

### Workflow 1: After Code Changes
```bash
# 1. Run conversation tests
make test-conversations

# 2. Check results
make test-results

# 3. If issues found, run specific category
make test-conversations-category CATEGORY=cross_turn_data_access
```

### Workflow 2: Before Release
```bash
# 1. Run all tests
make test

# 2. Check conversation test pass rate
cat tests/results/conversation_tests_latest.json | jq '.pass_rate'

# 3. Run full evaluation
make test-evaluation-full

# 4. Review both results before merging
```

### Workflow 3: Interactive Development
```bash
# Open notebook for AML knowledge testing
jupyter notebook notebooks/agent_evaluation_demo.ipynb

# Run conversation tests in terminal
make test-conversations

# Compare results side by side
```

---

## 🔄 Integration with CI/CD

### Recommended Pipeline

```yaml
test:
  script:
    # Run conversation tests (JSON output)
    - make test-conversations

    # Run evaluation tests (Python)
    - make test-evaluation

    # Check pass rates
    - python scripts/check_pass_rates.py

    # Fail if below threshold
    - if [ $(jq '.pass_rate' tests/results/conversation_tests_latest.json) < 0.8 ]; then exit 1; fi
```

---

## 🎯 Success Criteria

### Development
- Conversation tests: ≥70% pass rate
- Evaluation tests: ≥80% average score
- System tests: All pass

### Production
- Conversation tests: ≥90% pass rate
- Evaluation tests: ≥95% average score, no HIGH hallucinations
- System tests: 100% pass

---

## 📖 Documentation Map

- **This file**: Overview of all test types
- **tests/README.md**: Comprehensive testing guide
- **tests/evaluation/README.md**: Evaluation framework details
- **tests/results/README.md**: Conversation test results format
- **docs/TESTING_STRATEGY.md**: Overall testing strategy
- **notebooks/agent_evaluation_demo.ipynb**: Interactive evaluation demo

---

## ❓ FAQ

**Q: Which test produces JSON output?**
A: Only **Conversation Tests** automatically produce JSON. Evaluation tests CAN produce JSON if you manually save the report.

**Q: Where do I find the latest test results?**
A: `tests/results/conversation_tests_latest.json` for conversation tests. Evaluation tests don't auto-save.

**Q: Can I use the notebook for conversation tests?**
A: Not yet! The notebook currently only supports evaluation tests. You can add conversation tests to it manually.

**Q: How do I track test results over time?**
A: Conversation tests auto-save timestamped files in `tests/results/`. Use `make test-results-history` to see all runs.

**Q: What's the difference between evaluation and system tests?**
A: Evaluation tests check **AML knowledge** (typologies, red flags). System tests check **basic behavior** (off-topic, errors).

---

**Last Updated**: 2025-11-25
**Status**: Conversation Tests ✅ Complete | Evaluation Tests ✅ Complete | System Tests ⚠️ Basic
