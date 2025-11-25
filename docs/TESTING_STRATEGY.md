# Comprehensive Testing Strategy

## Overview

The AML Copilot system requires two distinct types of testing:

1. **Agent System Tests**: Testing the multi-agent orchestration, conversation management, routing
2. **AML Knowledge Tests**: Testing domain-specific compliance analysis quality

Both are critical for production readiness.

---

## 1. Agent System Tests

### Purpose
Validate that the multi-agent system functions correctly as a conversational AI system, independent of AML domain knowledge.

### Test Categories

#### A. Conversation Management

**Multi-Turn Conversations**
```json
{
  "test_id": "CONV_001",
  "category": "conversation",
  "description": "Multi-turn investigation with context retention",
  "turns": [
    {
      "user": "Tell me about customer C000123",
      "expected": "Should route to intent_mapper → data_retrieval"
    },
    {
      "user": "What about their transactions last month?",
      "expected": "Should understand 'their' refers to C000123"
    },
    {
      "user": "Any red flags?",
      "expected": "Should analyze previously retrieved data"
    }
  ]
}
```

**Context Retention**
- Does the agent remember previous queries?
- Can it resolve pronouns (their, it, those)?
- Does it maintain customer context across turns?

#### B. Out-of-Topic Handling

**Off-Topic Questions**
```json
{
  "test_id": "OFFTOPIC_001",
  "category": "boundaries",
  "user_query": "What's the weather today?",
  "expected_behavior": "Politely decline and explain scope"
}
```

**Boundary Tests**
- General knowledge questions
- Requests outside AML domain
- Personal questions
- Requests to do tasks agent can't perform

**Expected Responses**
- Polite decline: "I'm specialized in AML compliance analysis..."
- Clear boundaries: "I can help you with..."
- Redirect: "For customer analysis, I can..."

#### C. Coordinator Routing

**Routing Decision Tests**
```json
{
  "test_id": "ROUTE_001",
  "category": "routing",
  "scenarios": [
    {
      "query": "Show me customer C000123 profile",
      "expected_route": "intent_mapper"
    },
    {
      "query": "Review alert ALT_2024_001 and recommend disposition",
      "expected_route": "aml_alert_reviewer"
    },
    {
      "query": "What are the signs of structuring?",
      "expected_route": "compliance_expert"
    }
  ]
}
```

**Routing Accuracy**
- Does coordinator route to correct agent?
- Does it handle ambiguous queries?
- Does it ask for clarification when needed?

#### D. Error Handling

**Missing Data Scenarios**
```json
{
  "test_id": "ERROR_001",
  "category": "error_handling",
  "query": "Analyze customer C999999",
  "data_state": "customer_not_found",
  "expected_behavior": "Graceful error message, no hallucination"
}
```

**Error Types to Test**
- Customer not found
- Missing transaction data
- ML model unavailable
- Database connection errors
- Tool execution failures

**Expected Behaviors**
- Graceful error messages
- No hallucinated data
- Clear explanation of what's missing
- Suggestions for next steps

#### E. Review Loop Behavior

**Review Loop Tests**
```json
{
  "test_id": "REVIEW_001",
  "category": "review_loop",
  "description": "Agent iterates when review finds gaps",
  "initial_query": "Analyze customer C000123",
  "review_feedback": "needs_data: missing business verification",
  "expected": "Routes back to data_retrieval with additional_query"
}
```

**Loop Scenarios**
- needs_data → fetch additional data
- needs_refinement → improve analysis
- needs_clarification → ask user
- Loop prevention (max_review_attempts)

#### F. Intent Mapping Accuracy

**Entity Extraction Tests**
```json
{
  "test_id": "INTENT_001",
  "category": "intent_mapping",
  "query": "Show me transactions for customer C000123 from Jan 1 to Jan 31",
  "expected_entities": {
    "cif_no": "C000123",
    "date_range": {"start": "2024-01-01", "end": "2024-01-31"}
  },
  "expected_tools": ["get_customer_basic", "get_transaction_history"]
}
```

**Intent Types**
- data_query
- compliance_question
- alert_review
- procedural_guidance

---

## 2. AML Knowledge Tests

### Purpose
Validate that the agent produces accurate, compliant AML analysis (already implemented in golden test framework).

### Test Categories (Existing)

- Typology identification
- Red flag detection
- Risk assessment
- Regulatory citations
- Recommendation quality

---

## 3. Test Organization

### Directory Structure

```
tests/
├── system/                          # ✨ NEW: Agent system tests
│   ├── test_conversation.py         # Multi-turn conversations
│   ├── test_routing.py              # Coordinator routing
│   ├── test_error_handling.py       # Error scenarios
│   ├── test_review_loop.py          # Review loop behavior
│   ├── test_intent_mapping.py       # Entity extraction
│   └── test_boundaries.py           # Off-topic handling
│
├── evaluation/                      # ✅ EXISTING: AML knowledge tests
│   ├── test_runner.py               # Golden test suite runner
│   └── evaluators/                  # Specialized evaluators
│
└── fixtures/
    ├── golden_datasets/             # AML knowledge test cases
    └── system_test_cases/           # ✨ NEW: System behavior test cases
```

### Test Dataset Structure

**System Test Cases**
```json
{
  "test_id": "CONV_001",
  "category": "conversation",
  "priority": "HIGH",
  "conversation_turns": [
    {
      "turn": 1,
      "user_query": "Tell me about customer C000123",
      "expected_routing": "intent_mapper",
      "expected_entities": {"cif_no": "C000123"}
    },
    {
      "turn": 2,
      "user_query": "What about their recent transactions?",
      "expected_context_retention": ["C000123"],
      "expected_routing": "data_retrieval"
    }
  ]
}
```

---

## 4. Testing Priorities

### Phase 1: Critical System Tests (Week 1)
- [x] AML knowledge tests (completed - golden test framework)
- [ ] Out-of-topic handling
- [ ] Error handling (missing data)
- [ ] Coordinator routing accuracy

### Phase 2: Conversation Tests (Week 2)
- [ ] Multi-turn conversations (2-3 turns)
- [ ] Context retention
- [ ] Reference resolution (pronouns)

### Phase 3: Advanced System Tests (Week 3)
- [ ] Review loop behavior
- [ ] Intent mapping accuracy
- [ ] Complex error scenarios
- [ ] Edge case routing

### Phase 4: Load & Performance (Week 4)
- [ ] Response time benchmarks
- [ ] Token usage optimization
- [ ] Concurrent request handling

---

## 5. Test Execution Strategy

### Local Development
```bash
# Run AML knowledge tests (golden test suite)
pytest tests/evaluation/

# Run system tests
pytest tests/system/

# Run all tests
pytest tests/
```

### CI/CD Pipeline
```yaml
# Both test suites must pass
- AML Knowledge Tests (golden suite)
- Agent System Tests (routing, conversation, errors)
```

### Quality Gates

**For PR Approval:**
- ✓ All HIGH priority system tests pass
- ✓ AML knowledge test pass rate ≥ 95%
- ✓ No regressions in either test suite

**For Production Release:**
- ✓ 100% system test pass rate
- ✓ 100% golden test pass rate
- ✓ Expert review of sample outputs

---

## 6. Example System Test Cases

### Multi-Turn Conversation Test
```python
def test_multi_turn_customer_investigation():
    """Test that agent maintains context across conversation."""
    session_id = "test_session_001"

    # Turn 1: Initial query
    response1 = invoke_agent(
        "Tell me about customer C000123",
        session_id=session_id
    )
    assert "C000123" in response1.context["cif_no"]

    # Turn 2: Follow-up (pronoun reference)
    response2 = invoke_agent(
        "What about their transactions last month?",
        session_id=session_id
    )
    # Should retain C000123 from previous turn
    assert response2.context["cif_no"] == "C000123"
    assert "transaction" in response2.intent["intent_type"]

    # Turn 3: Analysis request
    response3 = invoke_agent(
        "Any red flags?",
        session_id=session_id
    )
    # Should analyze already-retrieved data
    assert response3.compliance_analysis is not None
```

### Off-Topic Handling Test
```python
def test_off_topic_handling():
    """Test that agent politely declines off-topic questions."""
    test_cases = [
        "What's the weather today?",
        "Tell me a joke",
        "Who won the World Series?",
        "How do I reset my password?"
    ]

    for query in test_cases:
        response = invoke_agent(query)

        # Should decline politely
        assert any(phrase in response.final_response.lower() for phrase in [
            "i'm specialized in aml",
            "i can help with",
            "outside my scope"
        ])

        # Should NOT attempt to answer
        assert not response.compliance_analysis
        assert not response.retrieved_data
```

### Error Handling Test
```python
def test_missing_customer_handling():
    """Test graceful handling of missing customer data."""
    response = invoke_agent("Analyze customer C999999")

    # Should have error message
    assert "not found" in response.final_response.lower() or \
           "unavailable" in response.final_response.lower()

    # Should NOT hallucinate data
    assert not response.compliance_analysis or \
           response.compliance_analysis.get("error")

    # Should NOT make up customer details
    # (Additional checks for hallucination)
```

---

## 7. Success Metrics

### Agent System Quality
- **Routing Accuracy**: ≥ 95% correct routing decisions
- **Context Retention**: ≥ 90% correct reference resolution
- **Error Handling**: 100% graceful (no crashes or hallucinations)
- **Boundary Respect**: 100% decline rate on off-topic queries

### AML Knowledge Quality (Existing)
- **Typology F1**: ≥ 0.90
- **Red Flag Recall**: ≥ 0.85
- **Pass Rate**: ≥ 95%

---

## 8. Next Steps

### Immediate (This Week)
1. Create system test fixtures (`tests/fixtures/system_test_cases/`)
2. Implement off-topic handling tests
3. Implement error handling tests
4. Implement basic routing tests

### Short-term (Next 2 Weeks)
5. Create multi-turn conversation tests
6. Add context retention tests
7. Implement review loop tests

### Medium-term (Next Month)
8. Performance benchmarking
9. Load testing
10. Complete test coverage analysis

---

## 9. Key Insight

**The AML Copilot needs two test suites:**

1. **"Is it a good AI assistant?"** → System tests (routing, conversation, errors)
2. **"Is it a good AML analyst?"** → Knowledge tests (typologies, compliance)

Both must pass for production readiness.
