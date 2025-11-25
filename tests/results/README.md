# Test Results Directory

This directory stores conversation test results for tracking system performance over time.

## File Structure

- **`conversation_tests_YYYYMMDD_HHMMSS.json`**: Timestamped test results
- **`conversation_tests_latest.json`**: Most recent test run results (committed to git)
- **`.gitkeep`**: Ensures directory exists in git

## Result Format

Each JSON file contains:
```json
{
  "timestamp": "2025-11-25T...",
  "fixture_path": "path/to/test_cases.json",
  "category_filter": null,
  "total": 13,
  "passed": 10,
  "failed": 3,
  "errors": 0,
  "pass_rate": 0.769,
  "category_stats": {
    "reference_resolution": {"total": 5, "passed": 4, ...},
    "cross_turn_data_access": {"total": 5, "passed": 4, ...},
    "context_accumulation": {"total": 3, "passed": 2, ...}
  },
  "results": [
    {
      "test_id": "CONV_REF_001",
      "category": "reference_resolution",
      "status": "PASS",
      "turn_results": [...],
      "error_message": null
    },
    ...
  ]
}
```

## Usage

### Run All Tests
```bash
cd /Users/souley/Desktop/code/aml_copilot
python tests/system/test_conversations.py
```

### Run Specific Category
```python
runner = ConversationTestRunner()
summary = runner.run_test_suite(
    fixture_path,
    category_filter="cross_turn_data_access"
)
```

### View Latest Results
```bash
cat tests/results/conversation_tests_latest.json | jq '.category_stats'
```

## Tracking Progress

Timestamped files allow you to track improvements over time:
1. Baseline: First run establishes baseline pass rate
2. After fixes: New run shows improvement
3. Regression detection: Pass rate drops indicate issues

Only `*_latest.json` files are committed to git to track current state without bloating the repository with historical data.

## Critical Tests

Tests marked with `"priority": "CRITICAL"` answer the key architectural question:
**"Is message history sufficient for cross-turn data synthesis?"**

Look for tests in the `cross_turn_data_access` category, especially:
- **CONV_DATA_002**: "Cross-reference synthesis - THE critical test"

If these pass with >80% rate, message history architecture is validated.
