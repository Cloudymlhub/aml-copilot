# AML Copilot API Test Plan

## Test Strategy
Each test is designed to validate specific agents and interaction patterns.

---

## Test Suite 1: Agent-Specific Tests

### Test 1.1: Coordinator - In-Scope Routing
**Objective:** Verify Coordinator correctly routes AML queries to Intent Mapper

**Query:** `"What is the customer's risk score?"`
**Expected Flow:** Coordinator → Intent Mapper → Data Retrieval → Compliance Expert → Review
**Expected Agents:**
- ✓ Coordinator (routing)
- ✓ Intent Mapper (tool selection)
- ✓ Data Retrieval (fetch risk data)
- ✓ Compliance Expert (analyze risk)
- ✓ Review Agent (quality check)

---

### Test 1.2: Coordinator - Out-of-Scope Handling
**Objective:** Verify Coordinator rejects non-AML queries with guidance

**Query:** `"What's the weather today?"`
**Expected Flow:** Coordinator → END (with guidance message)
**Expected Result:** Polite rejection explaining AML scope
**Expected Agents:**
- ✓ Coordinator only

---

### Test 1.3: Coordinator - Partial Scope (Banking → AML)
**Objective:** Verify Coordinator handles borderline queries with clarification

**Query:** `"Show me large cash deposits"`
**Expected Flow:** Coordinator → guidance OR Intent Mapper (if clarified)
**Expected Result:** Asks for AML-specific clarification
**Expected Agents:**
- ✓ Coordinator

---

### Test 1.4: Intent Mapper - Simple Tool Selection
**Objective:** Verify Intent Mapper selects correct single tool via bind_tools()

**Query:** `"Get basic customer information"`
**Expected Tool:** `get_customer_basic_info`
**Expected Agents:**
- ✓ Coordinator
- ✓ Intent Mapper (should select 1 tool)
- ✓ Data Retrieval
- ✓ Compliance Expert
- ✓ Review Agent

---

### Test 1.5: Intent Mapper - Multiple Tool Selection
**Objective:** Verify Intent Mapper can select multiple tools for complex queries

**Query:** `"Show me customer basic info, transaction patterns, and risk features"`
**Expected Tools:**
- `get_customer_basic_info`
- `get_customer_transaction_features`
- `get_customer_risk_features`
**Expected Agents:**
- ✓ Intent Mapper (should select 3+ tools)
- ✓ Data Retrieval (execute all tools)

---

### Test 1.6: Intent Mapper - Ambiguous Query Handling
**Objective:** Verify Intent Mapper requests clarification for vague queries

**Query:** `"Show me the data"`
**Expected Result:** Clarification request (no tool selection)
**Expected Flow:** Intent Mapper → END with clarification request

---

### Test 1.7: Data Retrieval - Tool Execution
**Objective:** Verify Data Retrieval correctly executes tools without interpretation

**Query:** `"Get transaction features for customer C000001"`
**Expected Behavior:**
- Execute tool mechanically
- Return structured data
- No interpretation/analysis
**Expected Agents:**
- ✓ Data Retrieval (mechanical execution)
- ✓ Compliance Expert (does interpretation)

---

### Test 1.8: Compliance Expert - Conceptual Question
**Objective:** Verify Compliance Expert answers AML questions without data retrieval

**Query:** `"What is structuring and how can it be detected?"`
**Expected Flow:** Coordinator → Compliance Expert → Review → END
**Expected Result:**
- No data retrieval
- Expert AML knowledge response
**Expected Agents:**
- ✓ Coordinator
- ✓ Compliance Expert (conceptual knowledge)
- ✓ Review Agent

---

### Test 1.9: Compliance Expert - Data Interpretation
**Objective:** Verify Compliance Expert interprets data through AML lens

**Query:** `"Analyze this customer for AML risk"`
**Expected Behavior:**
- Retrieve customer data
- Identify typologies
- Assess risk
- Provide recommendations
**Expected Agents:**
- ✓ All agents
- ✓ Compliance Expert (detailed analysis)

---

### Test 1.10: Review Agent - Pass (Good Response)
**Objective:** Verify Review Agent passes good responses

**Query:** `"What is the risk score for C000001?"`
**Expected Result:**
- Review status: "passed"
- Response sent to user
**Expected Agents:**
- ✓ Review Agent (passes first time)

---

## Test Suite 2: PEAR Loop Tests

### Test 2.1: Review Agent - needs_data (Full Replan)
**Objective:** Verify Review Agent triggers full replan when data is insufficient

**Setup:** Query that initially gets minimal data
**Query:** `"Analyze AML risk for C000001"` (but mock insufficient data response)
**Expected Flow:**
1. First attempt: Gets basic data
2. Review: needs_data → additional_query
3. Intent Mapper: Plans NEW query based on additional_query
4. Data Retrieval: Fetches additional data
5. Compliance Expert: Re-analyzes with ALL data
6. Review: passed

**Expected Agents:**
- ✓ Review Agent triggers replan
- ✓ Intent Mapper creates new plan
- ✓ Full pipeline executes again

---

### Test 2.2: Review Agent - needs_refinement (Partial Retry)
**Objective:** Verify Review Agent requests better analysis without new data

**Setup:** Good data retrieved but analysis is weak
**Expected Flow:**
1. First attempt: Data retrieved successfully
2. Compliance Expert: Provides analysis
3. Review: needs_refinement → feedback
4. Compliance Expert: Improves analysis with same data
5. Review: passed

**Expected Agents:**
- ✓ Review Agent requests refinement
- ✓ Compliance Expert retries (NO new data fetch)

---

### Test 2.3: Review Agent - needs_clarification
**Objective:** Verify Review Agent asks user for clarification

**Query:** `"Check the customer"` (too vague even after Intent Mapper)
**Expected Flow:**
1. Intent Mapper: Manages to select tools
2. Data Retrieval: Gets data
3. Compliance Expert: Provides analysis
4. Review: needs_clarification → question to user

**Expected Result:** User receives clarification request

---

### Test 2.4: Review Agent - Max Attempts Limit
**Objective:** Verify max_review_attempts prevents infinite loops

**Setup:** Query that keeps triggering needs_refinement
**Expected Behavior:**
- After MAX_REVIEW_ATTEMPTS (3), force completion
- Send best available response

---

## Test Suite 3: Session & Context Tests

### Test 3.1: Session Continuity - Basic
**Objective:** Verify conversation history is preserved across queries

**Queries (same session):**
1. `"Get basic info for C000001"`
2. `"What is their risk score?"` (should use context from Q1)
3. `"Show me their transactions"` (should continue context)

**Expected Behavior:**
- Session ID preserved
- Messages array grows
- Context maintained

---

### Test 3.2: Session Continuity - Follow-up Understanding
**Objective:** Verify agents understand follow-up questions

**Queries (same session):**
1. `"Analyze customer C000001 for AML risk"`
2. `"What typologies did you find?"` (reference to previous analysis)

**Expected Behavior:**
- Compliance Expert references previous analysis
- No re-fetching data (cached)

---

### Test 3.3: Session History Retrieval
**Objective:** Verify conversation history endpoint works

**Steps:**
1. Create session with 3 queries
2. Call GET `/api/sessions/{user_id}/{session_id}/history`
3. Verify all messages returned

---

### Test 3.4: Session Clearing
**Objective:** Verify sessions can be deleted

**Steps:**
1. Create session
2. DELETE `/api/sessions/{user_id}/{session_id}`
3. Verify session no longer accessible

---

## Test Suite 4: Data & Tools Tests

### Test 4.1: Customer Exists
**Objective:** Verify handling of valid customer IDs

**Query:** `"Get info for C000001"`
**Expected:** Successful data retrieval

---

### Test 4.2: Customer Not Found
**Objective:** Verify handling of invalid customer IDs

**Query:** `"Get info for C999999"`
**Expected:** Graceful error, recommendation to check ID

---

### Test 4.3: Multiple Customers (Batch)
**Objective:** Test system with multiple queries in sequence

**Queries:** C000001, C000002, C000003, C000004, C000005
**Expected:** All complete successfully with different risk profiles

---

### Test 4.4: Alert Investigation
**Objective:** Verify alert context is used

**Query:** `"Investigate alert ALT001 for customer C000001"`
**Context:** Include alert_id in payload
**Expected:** Alert-specific analysis

---

## Test Suite 5: Edge Cases & Error Handling

### Test 5.1: Empty Query
**Objective:** Verify handling of empty/whitespace queries

**Query:** `"   "`
**Expected:** Validation error

---

### Test 5.2: Missing Context (no cif_no)
**Objective:** Verify error when required context is missing

**Payload:** No cif_no in context
**Expected:** 400 error with clear message

---

### Test 5.3: Very Long Query
**Objective:** Verify handling of long queries

**Query:** 500+ word query about AML
**Expected:** Successful processing or timeout

---

### Test 5.4: Special Characters
**Objective:** Verify handling of special characters in queries

**Query:** `"What is C000001's risk? (High priority!)"`
**Expected:** Clean processing

---

### Test 5.5: Concurrent Requests (Optional)
**Objective:** Verify system handles multiple simultaneous requests

**Setup:** Send 5 queries in parallel
**Expected:** All complete successfully

---

## Test Suite 6: Cache & Performance

### Test 6.1: Cache Hit
**Objective:** Verify data caching works

**Steps:**
1. Query customer data (cold)
2. Query same customer again (warm)
3. Measure time difference

**Expected:** Second query faster

---

### Test 6.2: Cache Clear
**Objective:** Verify cache can be cleared

**Steps:**
1. Query data (cached)
2. POST `/api/cache/clear`
3. Query same data (should be slow again)

---

### Test 6.3: Performance Benchmarks
**Objective:** Measure response times by query type

**Queries:**
- Simple data: < 3 seconds
- Complex analysis: < 7 seconds
- Conceptual: < 4 seconds

---

## Test Execution Priority

### Phase 1: Core Functionality (Critical)
- Test 1.1, 1.4, 1.7, 1.8, 1.9
- Test 3.1, 3.3
- Test 4.1

### Phase 2: Advanced Features (High Priority)
- Test 2.1, 2.2, 2.3
- Test 1.2, 1.5, 1.6
- Test 4.2, 4.3

### Phase 3: Edge Cases (Medium Priority)
- All Test Suite 5
- Test 2.4
- Test 6.1, 6.2

### Phase 4: Performance (Low Priority)
- Test 6.3
- Test 5.5

---

## Success Criteria

### Critical (Must Pass)
- ✓ All agents execute in correct order
- ✓ Data retrieval works for valid customers
- ✓ Compliance analysis includes typologies & recommendations
- ✓ Session continuity maintained
- ✓ Out-of-scope queries rejected gracefully

### Important (Should Pass)
- ✓ PEAR loop triggers correctly
- ✓ Multiple tools selected when needed
- ✓ Ambiguous queries request clarification
- ✓ Cache improves performance

### Nice to Have (Bonus)
- ✓ Concurrent requests handled
- ✓ Performance within benchmarks
- ✓ All edge cases handled gracefully

---

## Test Tracking

| Test ID | Status | Response Time | Notes |
|---------|--------|---------------|-------|
| 1.1 | ⏳ | - | - |
| 1.2 | ⏳ | - | - |
| ... | | | |

Legend:
- ⏳ Not Started
- 🔄 In Progress
- ✅ Passed
- ❌ Failed
- ⚠️ Warning/Issue
