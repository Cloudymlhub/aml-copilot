# AML Copilot Agent Flow

## Architecture Overview

The AML Copilot uses a **LangGraph multi-agent system** with adaptive self-review capabilities. Agents collaborate to interpret queries, retrieve data, and provide compliance expertise with automatic quality assurance.

---

## Agent Roles

### 1. **Coordinator Agent**
- **Purpose**: Entry point and workflow orchestration
- **Responsibilities**:
  - Determines if query can be answered immediately
  - Routes to appropriate agent (intent_mapper or compliance_expert)
  - Handles simple greetings/help requests directly

### 2. **Intent Mapper Agent**
- **Purpose**: Natural language → structured query translation
- **Responsibilities**:
  - Parses user queries (original or additional data requests)
  - Identifies intent type (data_query, compliance_question, etc.)
  - Extracts entities and maps to feature groups
  - Determines which tools to invoke
  - Returns structured intent mapping

### 3. **Data Retrieval Agent**
- **Purpose**: Execute data queries using tools
- **Responsibilities**:
  - Executes tools specified by intent mapper
  - Fetches customer, transaction, alert, and report data
  - Returns structured data results
  - Handles tool execution errors

### 4. **Compliance Expert Agent**
- **Purpose**: AML domain expertise and analysis
- **Responsibilities**:
  - Interprets retrieved data through compliance lens
  - Identifies AML typologies and risks
  - Generates compliance analysis and recommendations
  - **Performs self-review** for quality assurance
  - Requests additional data if needed
  - Synthesizes final user-facing response

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      USER SUBMITS QUERY                      │
│              (with context: cif_no, alert_id, etc.)          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   COORDINATOR        │ Entry point
              │   (Agent 1)          │
              └──────────┬───────────┘
                         │
                         ├─→ Simple query? → Direct response → END
                         │
                         ▼
              ┌──────────────────────┐
              │   INTENT MAPPER      │ Parse query
              │   (Agent 2)          │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   DATA RETRIEVAL     │ Fetch data
              │   (Agent 3)          │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  COMPLIANCE EXPERT   │ Analyze + Review
              │   (Agent 4)          │
              │                      │
              │  1. Generate analysis│
              │  2. Self-review      │
              │  3. Set review_status│
              └──────────┬───────────┘
                         │
                         ▼
           ┌─────────────────────────────┐
           │   ROUTE AFTER COMPLIANCE    │ Decision point
           │   (Graph conditional edge)  │
           └─┬───────────┬───────────┬───┘
             │           │           │
    ┌────────┘           │           └────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌────────┐    ┌──────────────────┐    ┌─────────────┐
│  END   │    │  INTENT MAPPER   │    │ COMPLIANCE  │
│(passed)│    │  (needs_data)    │    │   EXPERT    │
└────────┘    │                  │    │(needs_refine)│
              │ Re-interpret     │    └──────┬──────┘
              │ additional_query │           │
              └────────┬─────────┘           │
                       │                     │
                       ▼                     │
            ┌──────────────────┐            │
            │  DATA RETRIEVAL  │            │
            │  (fetch more)    │            │
            └────────┬─────────┘            │
                     │                      │
                     └──────────────────────┘
                              │
                              ▼
                   [Loop back to Compliance Expert]
```

---

## Detailed Flow Steps

### **Initial Pass (First Request)**

1. **User Query** → Coordinator
   - Input: `user_query`, `context` (cif_no, alert_id, etc.)
   
2. **Coordinator** → Intent Mapper
   - Decision: Is this a simple query? No → route to intent_mapper
   
3. **Intent Mapper** → Data Retrieval
   - Parses `user_query`
   - Returns: `intent` (tools_to_use, entities, feature_groups)
   
4. **Data Retrieval** → Compliance Expert
   - Executes tools from intent
   - Returns: `retrieved_data` (customer info, transactions, alerts, etc.)
   
5. **Compliance Expert** → Self-Review
   - Generates compliance analysis
   - Synthesizes final response
   - **Performs self-review**:
     - ✅ Complete? Accurate? Clear? Actionable?
     - Returns: `review_status` + `review_feedback` + `additional_query` (if needed)

### **Review Decision Point**

The graph routes based on `review_status`:

#### **Option A: Review Passed** ✅
```
review_status = "passed"
→ END
→ Return final_response to user
```

#### **Option B: Needs Additional Data** 🔄
```
review_status = "needs_data"
additional_query = "Get the customer's transaction history for last 6 months"

→ Route to Intent Mapper (with additional_query as new user_query)
→ Intent Mapper interprets the additional data request
→ Data Retrieval fetches MORE data
→ Compliance Expert re-analyzes with COMBINED data (old + new)
→ Self-review again
→ [Loop until passed or max attempts]
```

#### **Option C: Needs Refinement** 🔁
```
review_status = "needs_refinement"
review_feedback = "Analysis is too shallow, need to address typology X"

→ Route back to Compliance Expert (with same data + feedback)
→ Compliance Expert regenerates response with feedback guidance
→ Self-review again
→ [Loop until passed or max attempts]
```

---

## Self-Review Criteria

The Compliance Expert evaluates its own response against:

1. **Completeness**: Does it fully answer the user's question?
2. **Data Sufficiency**: Is there enough data to provide accurate analysis?
3. **Accuracy**: Are facts, figures, and typologies correct?
4. **Clarity**: Is the response clear and well-structured?
5. **Regulatory Compliance**: Are regulatory references appropriate?
6. **Actionability**: Does it provide clear next steps?

### Review Outcomes:

| Status | Meaning | Action |
|--------|---------|--------|
| `passed` | Response meets all quality standards | Return to user |
| `needs_data` | Missing critical information | Request additional data via intent mapper |
| `needs_refinement` | Analysis quality issues | Regenerate with feedback |

---

## State Management

### Key State Fields:

```python
# Core
user_query: str                    # Current query being processed
context: Dict[str, Any]           # Customer context (cif_no, alert_id, etc.)

# Agent Outputs
intent: IntentMapping             # From intent mapper
retrieved_data: DataRetrievalResult  # From data retrieval
compliance_analysis: ComplianceAnalysis  # From compliance expert
final_response: str               # User-facing response

# Self-Review (NEW)
review_status: "passed" | "needs_data" | "needs_refinement"
review_feedback: str              # Why review failed
additional_query: Optional[str]   # Natural language request for missing data
review_attempts: int              # Number of review iterations

# Routing
next_agent: str                   # Which agent to route to
current_step: str                 # Current workflow step
completed: bool                   # Workflow finished?
```

---

## Adaptive Capabilities

### 🔄 **Automatic Data Enrichment**
If the expert realizes mid-analysis that it needs more data:
- Generates natural language query: `"Get alert investigation notes for alert A123"`
- Intent mapper translates to tool calls
- System fetches additional data automatically
- Expert continues with enriched context

### 🎯 **Quality Assurance**
Every response is self-reviewed before reaching the user:
- Catches incomplete analyses
- Identifies missing data early
- Ensures compliance standards are met

### 🛡️ **Safety Limits**
- `MAX_REVIEW_ATTEMPTS = 3` (configurable)
- After max attempts, returns best effort response
- Prevents infinite loops

---

## Configuration

Each agent uses configurable LLM settings:

```python
# .env configuration
COORDINATOR_MODEL=gpt-4o          # Orchestration
INTENT_MAPPER_MODEL=gpt-4o        # Query understanding
DATA_RETRIEVAL_MODEL=gpt-4o-mini  # Tool execution (simpler)
COMPLIANCE_EXPERT_MODEL=gpt-4o    # Domain expertise (most critical)

# Per-agent settings
- model_name
- temperature
- max_retries
- timeout
```

---

## Checkpointing & Sessions

- **Redis Checkpointer** (db=1): Stores conversation state
- **Session-based**: Each user session maintains separate state
- **Resumable**: Conversations can be continued across requests
- **Cache-separate**: Data cache (db=0) isolated from checkpoints (db=1)

---

## Error Handling

### Tool Execution Errors
- Data retrieval agent catches tool failures
- Returns partial data with error messages
- Compliance expert can request retry or work with partial data

### Review Failures
- If self-review fails to parse: assume "passed" (fail-safe)
- If max attempts exceeded: return final_response with warning
- All review attempts logged in state

### LLM Failures
- Each agent has `max_retries` configuration
- Timeouts prevent hanging
- Graceful degradation to simpler responses

---

## Future Enhancements

- [ ] Human-in-the-loop approval (using LangGraph interrupts)
- [ ] Multi-turn conversation memory
- [ ] Tool recommendation learning
- [ ] Dynamic feature group selection
- [ ] Compliance rule engine integration

---

## See Also

- [Architecture Documentation](./ARCHITECTURE.md)
- [Implementation Plan](./objective.md)
- [API Documentation](./api/README.md)
