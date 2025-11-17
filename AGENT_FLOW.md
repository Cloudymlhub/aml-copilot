# AML Copilot Agent Flow

## Overview
This document describes the multi-agent workflow for the AML Compliance Copilot system, including the dedicated ReviewAgent and clarification mechanisms.

## Agents

### 1. Coordinator Agent
**Role**: Entry point, scope validation, and workflow orchestration

**Responsibilities**:
- **Scope Validation**: Determines if query is AML-related (in-scope vs out-of-scope)
- Routes in-scope queries to appropriate agents
- Rejects out-of-scope queries with helpful messages

**Outputs**:
- `in_scope`: boolean
- `out_of_scope_message`: helpful rejection message (if out-of-scope)
- `next_agent`: "intent_mapper" | "compliance_expert" | "end"

**Routing Logic**:
- OUT OF SCOPE → `end` (return rejection message)
- Data query → `intent_mapper`
- Compliance question (no data needed) → `compliance_expert`
- Procedural guidance → `compliance_expert`

---

### 2. Intent Mapper Agent
**Role**: Natural language to structured query mapping

**Responsibilities**:
- Interprets user queries (or additional_query from ReviewAgent)
- Extracts entities and maps to tools
- **Clarification Check**: Identifies ambiguous queries

**Outputs**:
- `needs_clarification`: boolean
- `clarification_question`: natural language question (if ambiguous)
- `intent`: Structured mapping with tools and arguments
- `tools_to_use`: List of tools to invoke

**Routing Logic**:
- NEEDS CLARIFICATION → `end` (return clarification question to user)
- MAPPABLE → `data_retrieval`

---

### 3. Data Retrieval Agent
**Role**: Execute data queries using tools

**Responsibilities**:
- Invokes tools specified by Intent Mapper
- Retrieves factual data without interpretation
- Handles errors gracefully

**Outputs**:
- `retrieved_data`: Success/failure with data
- `tools_used`: List of executed tools

**Routing Logic**:
- Always → `compliance_expert`

---

### 4. Compliance Expert Agent
**Role**: AML domain expertise and analysis

**Responsibilities**:
- Interprets retrieved data through AML lens
- Identifies typologies and risk patterns
- Provides recommendations and regulatory references
- Incorporates review feedback on retries

**Outputs**:
- `compliance_analysis`: Structured analysis
- `final_response`: Natural language response

**Routing Logic**:
- Always → `review_agent`

---

### 5. Review Agent (NEW)
**Role**: Quality assurance and adaptive routing

**Responsibilities**:
- Evaluates compliance expert output objectively
- Identifies missing data, quality issues, or ambiguities
- Determines next steps based on review criteria

**Review Criteria**:
1. **Completeness**: Does it fully answer the query?
2. **Data Sufficiency**: Is critical data missing?
3. **Accuracy**: Are insights and typologies correct?
4. **Clarity**: Is the response understandable?
5. **Actionability**: Are next steps clear?
6. **Query Clarity**: Is the original question clear enough?

**Outputs**:
- `review_status`: "passed" | "needs_data" | "needs_refinement" | "needs_clarification" | "human_review"
- `review_feedback`: Detailed explanation
- `additional_query`: Natural language request (for needs_data or needs_clarification)
- `confidence`: 0.0-1.0

**Routing Logic**:
- **passed** → `end` (return to user)
- **needs_data** → `intent_mapper` (fetch more data)
- **needs_refinement** → `compliance_expert` (redo analysis)
- **needs_clarification** → `end` (ask user for clarification)
- **human_review** → `end` (flag for human intervention)
- **max_attempts (3)** → `end` (force completion)

---

## Complete Flow Diagram

```
START
  ↓
┌─────────────┐
│ Coordinator │ (Scope validation)
└─────────────┘
  ↓
  ├─ OUT OF SCOPE ────────────────────────────────────→ END (rejection message)
  │
  ├─ Compliance question (no data) ──→ Compliance Expert
  │
  └─ Data query
       ↓
  ┌──────────────┐
  │ Intent Mapper │ (Map query to tools, check clarity)
  └──────────────┘
       ↓
       ├─ NEEDS CLARIFICATION ──────────────────────────→ END (clarification question)
       │
       └─ MAPPABLE
            ↓
       ┌────────────────┐
       │ Data Retrieval  │ (Execute tools)
       └────────────────┘
            ↓
       ┌────────────────────┐
       │ Compliance Expert  │ (Analyze & synthesize)
       └────────────────────┘
            ↓
       ┌──────────────┐
       │ Review Agent │ (QA evaluation)
       └──────────────┘
            ↓
            ├─ PASSED ──────────────────────────────────→ END (success)
            │
            ├─ NEEDS DATA ──────────────────────────────→ Intent Mapper (loop with additional_query)
            │
            ├─ NEEDS REFINEMENT ────────────────────────→ Compliance Expert (retry with feedback)
            │
            ├─ NEEDS CLARIFICATION ─────────────────────→ END (ask user)
            │
            ├─ HUMAN REVIEW ────────────────────────────→ END (flag for human)
            │
            └─ MAX ATTEMPTS (3) ────────────────────────→ END (force completion)
```

---

## Adaptive Loops

### Loop 1: Additional Data Loop
```
Compliance Expert → Review Agent (needs_data) → Intent Mapper → Data Retrieval → Compliance Expert
```
**Trigger**: ReviewAgent identifies missing critical data
**Mechanism**: `additional_query` is set to natural language data request
**Example**: "I need the customer's transaction history for the past 6 months"

### Loop 2: Refinement Loop
```
Compliance Expert → Review Agent (needs_refinement) → Compliance Expert
```
**Trigger**: ReviewAgent finds quality issues (wrong typology, unclear explanation)
**Mechanism**: `review_feedback` provides specific improvement guidance
**Example**: "The structuring typology is incorrectly identified; transactions don't match the pattern"

### Loop 3: Clarification Loop
```
Intent Mapper (ambiguous query) → END (clarification request to user)
Review Agent (needs_clarification) → END (clarification request to user)
```
**Trigger**: Query is too ambiguous to process
**Mechanism**: Return `clarification_question` to user
**Example**: "Please clarify: are you asking about alert A123 or the customer's overall profile?"

---

## Safety Mechanisms

### 1. Max Attempts Limit
- **Limit**: 3 review cycles total
- **Trigger**: `review_attempts >= 3`
- **Action**: Force `passed` status and return current response
- **Purpose**: Prevent infinite loops

### 2. Scope Validation
- **Trigger**: Query is not AML/compliance-related
- **Action**: Return rejection message immediately
- **Purpose**: Prevent misuse and wasted resources

### 3. Fail-Safe Review
- **Trigger**: ReviewAgent JSON parsing fails
- **Action**: Default to `passed` with low confidence
- **Purpose**: System continues even with review errors

---

## Example Scenarios

### Scenario 1: Simple Data Query (Success)
```
User: "What is the risk score for customer C000123?"

1. Coordinator: in_scope=true → intent_mapper
2. Intent Mapper: Maps to get_customer_risk_features → data_retrieval
3. Data Retrieval: Fetches risk_score=85 → compliance_expert
4. Compliance Expert: "Customer C000123 has a risk score of 85 (High)" → review_agent
5. Review Agent: review_status=passed → END
```

### Scenario 2: Missing Data Loop
```
User: "Assess alert A456 for customer C000123"

1. Coordinator → Intent Mapper → Data Retrieval → Compliance Expert
2. Compliance Expert: Generates initial response → review_agent
3. Review Agent: "Missing transaction history needed to assess alert" 
   - review_status=needs_data
   - additional_query="Get all transactions for customer C000123 in the past 6 months"
4. Intent Mapper: (processes additional_query) → data_retrieval
5. Data Retrieval: Fetches transactions → compliance_expert
6. Compliance Expert: Complete assessment with transaction data → review_agent
7. Review Agent: review_status=passed → END
```

### Scenario 3: Out of Scope
```
User: "What's the weather today?"

1. Coordinator: in_scope=false 
   - out_of_scope_message="I'm an AML compliance assistant..."
   → END
```

### Scenario 4: Ambiguous Query
```
User: "Show me the data"

1. Coordinator → Intent Mapper
2. Intent Mapper: needs_clarification=true
   - clarification_question="Which data would you like to see? Please specify: customer info, transactions, alerts, or risk features?"
   → END
```

### Scenario 5: Refinement Loop
```
User: "Is this customer involved in structuring?"

1-4. (Normal flow through data retrieval and compliance expert)
5. Review Agent: "Incorrectly identified structuring - transactions don't show amounts near $10k threshold"
   - review_status=needs_refinement
   - review_feedback="Re-evaluate typology. Check if transaction pattern actually matches structuring definition."
6. Compliance Expert: (retries with feedback) → review_agent
7. Review Agent: review_status=passed → END
```

---

## Configuration

Each agent can be configured with:
- `model_name`: LLM model to use
- `temperature`: Creativity/randomness (0.0-1.0)
- `max_retries`: API retry attempts
- `timeout`: Request timeout

Review Agent uses the same config as Compliance Expert by default.

---

## References

- State Schema: `agents/state.py`
- Prompts: `agents/prompts.py`
- Graph Definition: `agents/graph.py`
- Individual Agents: `agents/*.py`
