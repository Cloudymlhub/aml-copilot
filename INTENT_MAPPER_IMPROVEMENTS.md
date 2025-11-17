# Intent Mapper Improvements - Future Enhancement

**Status:** 📋 TODO - High Priority
**Estimated Effort:** 2-3 hours
**Impact:** Schema validation, reduced errors, auto-sync with tools
**Dependencies:** None (standalone improvement)

---

## Executive Summary

The Intent Mapper currently uses **static tool descriptions** in its prompt, which creates maintenance overhead and risks tool name hallucination. This enhancement will implement **OpenAI Function Calling** via `bind_tools()` to give the Intent Mapper schema-aware access to tools while maintaining the clean separation between planning and execution.

**Key Benefits:**
- ✅ Automatic schema validation (no tool name hallucinations)
- ✅ Auto-sync with tool registry (no manual prompt updates)
- ✅ Type-safe argument validation
- ✅ Production-ready reliability

**No Architecture Changes:** Intent Mapper remains the planner, Data Retrieval remains the executor.

---

## Current State Analysis

### Architecture (Correct - No Changes Needed)

```
┌─────────────────────────────────────────────────────────────┐
│ Intent Mapper Agent (Planning)                              │
│ - Uses LLM (gpt-4o-mini)                                   │
│ - Receives: User query                                      │
│ - Outputs: JSON with tools_to_use                          │
│ - Has NO direct access to tools                            │
│ - Tool knowledge via STATIC PROMPT ← PROBLEM               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ Writes to state:
                      │ {
                      │   "tools_to_use": [
                      │     {"tool": "get_customer_basic_info",
                      │      "args": {"cif_no": "C000001"}}
                      │   ]
                      │ }
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ Data Retrieval Agent (Execution)                            │
│ - NO LLM involved (mechanical execution)                    │
│ - Loads ALL 17 tools via get_all_tools()                   │
│ - Creates tool_map for lookup                              │
│ - Executes tools by name from intent                       │
└─────────────────────────────────────────────────────────────┘
```

**What's Good:**
- ✅ Clean separation: Planning vs Execution
- ✅ State-based communication
- ✅ Well-organized tool registry

**What Needs Improvement:**
- ❌ Static tool inventory in prompt (manual maintenance)
- ❌ No schema validation (can hallucinate tool names/args)
- ❌ Drift risk (prompt out of sync with actual tools)

---

## Problems Addressed

### Problem 1: Static Tool Inventory

**Current:**
```python
INTENT_MAPPER_PROMPT = """...
Available tools:
Customer tools:
- get_customer_basic_info: Get basic customer information
- get_customer_transaction_features: Get transaction aggregation features
...
"""
```

**Issues:**
- Manual maintenance when adding/removing tools
- Prompt can drift from actual tool registry
- No schema awareness (just descriptions)

**Example Failure:**
```python
# Developer adds new tool
class GetCustomerSanctionsCheck(BaseTool):
    name = "get_customer_sanctions_check"
    ...

# But forgets to update INTENT_MAPPER_PROMPT
# → LLM never suggests this tool
# → Users can't access sanctions data
```

### Problem 2: Tool Name Hallucination

**Current:**
```python
# LLM can invent tool names:
{
  "tools_to_use": [
    {"tool": "get_customer_info", "args": {...}}  # ❌ Wrong name!
  ]
}

# Data Retrieval Agent fails:
if tool_name not in self.tool_map:
    return {"error": f"Tool '{tool_name}' not found"}
```

### Problem 3: Argument Schema Mismatch

**Current:**
```python
# LLM generates wrong arg names:
{"tool": "get_customer_basic_info", "args": {"customer_id": "C001"}}
# ❌ Should be "cif_no", not "customer_id"

# Execution fails with TypeError
tool._run(**args)  # TypeError: unexpected keyword argument 'customer_id'
```

---

## Proposed Solution: OpenAI Function Calling

### Implementation with `bind_tools()`

**Concept:**
```python
# Intent Mapper uses bind_tools() to SEE tools (planning)
# Data Retrieval Agent EXECUTES tools (no change)
# Clean separation maintained!
```

**How `bind_tools()` Works:**

From LangChain docs:
> "bind_tools() does not execute tools—it only prepares the model to recognize and return tool invocation information."

When you call `bind_tools()`:
1. LLM sees actual tool schemas (names, descriptions, argument types)
2. LLM returns tool call metadata (name + args)
3. OpenAI validates arguments match schema
4. **Tools are NOT executed** (that's still Data Retrieval's job)

**Code Example:**
```python
class IntentMappingAgent:
    def __init__(self, config: AgentConfig):
        self.llm = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
        )

        # Get actual tools from registry
        self.available_tools = get_all_tools()  # 17 tools

        # Bind tools to LLM (for planning only!)
        self.llm_with_tools = self.llm.bind_tools(self.available_tools)

    def __call__(self, state: AMLCopilotState):
        messages = [
            SystemMessage(content="You are a planner. Select tools to answer the query."),
            HumanMessage(content=f"Query: {state['user_query']}\nCIF: {state['context']['cif_no']}")
        ]

        # LLM returns tool call METADATA (not execution results!)
        response = self.llm_with_tools.invoke(messages)

        # Extract the plan
        tools_to_use = [
            {"tool": tc["name"], "args": tc["args"]}
            for tc in response.tool_calls  # ← Validated by OpenAI!
        ]

        # Pass plan to Data Retrieval Agent (no change)
        return {
            "intent": {
                "tools_to_use": tools_to_use,
                ...
            },
            "next_agent": "data_retrieval"
        }
```

**What Changes:**
- Intent Mapper uses `bind_tools()` instead of static prompt
- Tool schemas auto-loaded from registry
- OpenAI validates tool calls before returning

**What Doesn't Change:**
- Data Retrieval Agent still executes tools
- State-based communication preserved
- Plan-and-execute pattern unchanged

---

## Benefits

### 1. Automatic Schema Validation

**Before:**
```python
# LLM can hallucinate:
{"tool": "get_customer_info", "args": {"customer_id": "C001"}}  # ❌
```

**After:**
```python
# OpenAI only allows real tools with correct schemas:
{"tool": "get_customer_basic_info", "args": {"cif_no": "C001"}}  # ✅
# Validated against actual tool.args_schema!
```

### 2. Auto-Sync with Tool Registry

**Before:**
```python
# Add new tool
tools/customer_tools.py: + GetCustomerSanctionsCheck
agents/prompts.py: + "- get_customer_sanctions_check: ..."  # Manual!
```

**After:**
```python
# Add new tool
tools/customer_tools.py: + GetCustomerSanctionsCheck
# Done! Intent Mapper automatically sees it via bind_tools()
```

### 3. Type Safety

**Before:**
```python
# LLM can use wrong types:
{"args": {"cif_no": 12345}}  # ❌ Should be string
```

**After:**
```python
# OpenAI enforces type from schema:
Tool.args_schema = {"cif_no": {"type": "string"}}
# LLM can only generate: {"args": {"cif_no": "12345"}}  # ✅
```

### 4. Better Error Messages

**Before:**
```python
# Vague errors:
"Tool 'get_customer_info' not found"
```

**After:**
```python
# Schema validation errors:
"Tool 'get_customer_basic_info' expects argument 'cif_no' (string), got 'customer_id'"
```

---

## Implementation Plan

### Phase 1: Quick Win - Dynamic Prompt (30 minutes)

**Goal:** Eliminate manual prompt maintenance

**Changes:**
```python
# agents/intent_mapper.py
class IntentMappingAgent:
    def __init__(self, config: AgentConfig):
        self.tools = get_all_tools()
        self.tools_description = self._build_tools_description()

    def _build_tools_description(self) -> str:
        """Generate tools section from actual tools."""
        return "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self.tools
        ])

    def __call__(self, state):
        # Use dynamic prompt
        prompt = INTENT_MAPPER_TEMPLATE.format(
            available_tools=self.tools_description,
            user_query=user_query
        )
```

**Benefit:** Tools auto-described, no manual updates

### Phase 2: Add Validation (1 hour)

**Goal:** Catch hallucinated tool names early

**Changes:**
```python
class IntentMappingAgent:
    def __init__(self, config):
        self.tools = get_all_tools()
        self.valid_tool_names = {tool.name for tool in self.tools}

    def __call__(self, state):
        # ... get intent from LLM ...

        # Validate tool names exist
        for tool_spec in intent["tools_to_use"]:
            tool_name = tool_spec.get("tool")
            if tool_name not in self.valid_tool_names:
                raise ValueError(f"Unknown tool: {tool_name}. Available: {self.valid_tool_names}")
```

**Benefit:** Fail fast with clear error messages

### Phase 3: Function Calling (2-3 hours) ⭐ **Recommended**

**Goal:** Full schema validation, production-ready

**Changes:**
```python
class IntentMappingAgent:
    def __init__(self, config: AgentConfig):
        self.llm = ChatOpenAI(...)
        self.available_tools = get_all_tools()

        # Enable function calling
        self.llm_with_tools = self.llm.bind_tools(self.available_tools)

    def __call__(self, state: AMLCopilotState):
        # Handle replanning
        query = state.get("additional_query") or state["user_query"]

        messages = [
            SystemMessage(content="""You are an intent mapper for AML compliance.

            Analyze the user query and select the appropriate tools to retrieve data.
            You can call multiple tools if needed.

            Always include the customer's CIF number in tool arguments.
            """),
            HumanMessage(content=f"Query: {query}\nCIF: {state['context']['cif_no']}")
        ]

        # LLM uses function calling (returns validated tool calls)
        response = self.llm_with_tools.invoke(messages)

        # Extract tool calls (already validated by OpenAI!)
        tools_to_use = [
            {"tool": tc["name"], "args": tc["args"]}
            for tc in response.tool_calls
        ]

        # Build intent
        intent = {
            "intent_type": "data_query",
            "tools_to_use": tools_to_use,
            "confidence": 0.9,  # Higher confidence with schema validation
            "entities": {"cif_no": state['context']['cif_no']}
        }

        return {
            "intent": intent,
            "next_agent": "data_retrieval",
            ...
        }
```

**Files Modified:**
- `agents/intent_mapper.py` - Use bind_tools()
- `agents/prompts.py` - Simplify INTENT_MAPPER_PROMPT (remove tool list)

**Testing:**
```python
# Test: Can only call real tools
def test_no_hallucination():
    response = intent_mapper({"user_query": "Get customer data", "context": {"cif_no": "C001"}})
    # All tools in response.intent.tools_to_use must exist in registry
    assert all(t["tool"] in valid_tool_names for t in response["intent"]["tools_to_use"])

# Test: Argument validation
def test_correct_arguments():
    response = intent_mapper({"user_query": "Get basic info", "context": {"cif_no": "C001"}})
    # Tool args must match schema
    for tool_call in response["intent"]["tools_to_use"]:
        if tool_call["tool"] == "get_customer_basic_info":
            assert "cif_no" in tool_call["args"]  # Required arg
            assert isinstance(tool_call["args"]["cif_no"], str)  # Correct type
```

**Benefit:** Production-ready with full validation

---

## LangChain Pattern Alignment

### Plan-and-Execute Pattern with Function Calling

**From LangChain docs:**
> "The plan-and-execute pattern consists of two basic components: A planner, which prompts an LLM to generate a multi-step plan to complete a large task, and Executor(s), which accept the user query and a step in the plan and invoke 1 or more tools to complete that task."

**Our Implementation:**
```
Intent Mapper (Planner with bind_tools) → Data Retrieval (Executor)
```

**Key Insight from LangChain:**
> "bind_tools() does not execute tools—it only prepares the model to recognize and return tool invocation information."

This is **exactly** our pattern! Intent Mapper plans, Data Retrieval executes.

**References:**
- [LangChain Tool Calling](https://python.langchain.com/docs/concepts/tool_calling/)
- [LangChain Plan-and-Execute](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/)
- [Tool Calling Blog Post](https://blog.langchain.com/tool-calling-with-langchain/)

---

## Testing Strategy

### Unit Tests

```python
# Test: Dynamic tool loading
def test_tools_auto_loaded():
    agent = IntentMappingAgent(config)
    assert len(agent.available_tools) == 17  # Current count
    assert "get_customer_basic_info" in [t.name for t in agent.available_tools]

# Test: Tool call validation
def test_valid_tool_calls():
    state = {"user_query": "Get risk score", "context": {"cif_no": "C001"}}
    result = agent(state)
    tools = result["intent"]["tools_to_use"]

    # All tools must exist
    for tool_call in tools:
        assert tool_call["tool"] in valid_tool_names

# Test: Argument schema validation
def test_argument_types():
    state = {"user_query": "Get basic info", "context": {"cif_no": "C001"}}
    result = agent(state)

    for tool_call in result["intent"]["tools_to_use"]:
        if tool_call["tool"] == "get_customer_basic_info":
            assert isinstance(tool_call["args"]["cif_no"], str)
```

### Integration Tests

```python
# Test: End-to-end with Data Retrieval
def test_planning_and_execution():
    # Intent Mapper creates plan
    intent_result = intent_mapper(state)

    # Data Retrieval executes plan
    data_result = data_retrieval(intent_result)

    # Execution succeeds (no "tool not found" errors)
    assert data_result["retrieved_data"]["success"] == True
```

---

## Migration Checklist

- [ ] **Phase 1: Dynamic Prompt**
  - [ ] Add `self.available_tools = get_all_tools()` to `__init__`
  - [ ] Implement `_build_tools_description()` method
  - [ ] Update prompt to use dynamic tool list
  - [ ] Test: Tools auto-sync

- [ ] **Phase 2: Validation**
  - [ ] Add tool name validation
  - [ ] Add tests for unknown tool detection
  - [ ] Test: Clear error messages

- [ ] **Phase 3: Function Calling** ⭐
  - [ ] Replace LLM with `llm.bind_tools(self.available_tools)`
  - [ ] Update `__call__` to extract `response.tool_calls`
  - [ ] Simplify prompt (remove tool descriptions)
  - [ ] Add schema validation tests
  - [ ] Update documentation

- [ ] **Documentation**
  - [ ] Update `ARCHITECTURE.md` with new Intent Mapper implementation
  - [ ] Add code comments explaining bind_tools usage
  - [ ] Update API documentation

---

## Performance Impact

**No negative impact expected:**

**Before (Static Prompt):**
```
LLM call with ~1500 token prompt (includes all tool descriptions)
```

**After (Function Calling):**
```
LLM call with ~500 token prompt (tool schemas sent via function calling format)
OpenAI handles schema validation (built-in, no extra cost)
```

**Net Result:** ~1000 fewer tokens per request = **cost savings**

---

## Risks & Mitigation

### Risk 1: Breaking Change

**Concern:** Changing Intent Mapper might break existing flows

**Mitigation:**
- Incremental rollout (Phase 1 → 2 → 3)
- Comprehensive testing at each phase
- Can rollback to previous phase if issues found

### Risk 2: OpenAI-Specific

**Concern:** Tied to OpenAI's function calling

**Mitigation:**
- Already using OpenAI for all agents
- `bind_tools()` is LangChain abstraction (works with other providers)
- Can fallback to Phase 2 (validation without function calling) if needed

### Risk 3: Schema Changes

**Concern:** Tool schema changes might break Intent Mapper

**Mitigation:**
- Pydantic tool schemas are versioned
- Schema changes are code changes (tested)
- Function calling fails gracefully with clear errors

---

## Success Criteria

**After implementation:**

1. ✅ **Zero Manual Prompt Updates**
   - Add new tool → Automatically available to Intent Mapper

2. ✅ **Zero Tool Name Hallucinations**
   - LLM can only suggest tools that exist

3. ✅ **Zero Type Errors**
   - Arguments validated against tool schemas

4. ✅ **Clear Error Messages**
   - When validation fails, error indicates what's wrong

5. ✅ **Tests Pass**
   - Unit tests for tool loading, validation
   - Integration tests for planning → execution

---

## Related Documentation

**Implementation References:**
- Current: `agents/intent_mapper.py`
- Current: `agents/prompts.py` - `INTENT_MAPPER_PROMPT`
- Current: `tools/registry.py` - `get_all_tools()`

**Architecture:**
- `ARCHITECTURE.md` - Multi-Agent System section
- `ARCHITECTURE.md` - Plan-Execute-Analyze-Review-Replan Pattern

**LangChain Docs:**
- [Tool Calling Concepts](https://python.langchain.com/docs/concepts/tool_calling/)
- [Plan-and-Execute Tutorial](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/)
- [Function Calling Blog](https://blog.langchain.com/tool-calling-with-langchain/)

---

## Decision: Proceed?

**Recommendation:** ✅ **YES - Implement Phase 3 (Function Calling)**

**Rationale:**
- High impact (eliminates entire class of errors)
- Low risk (incremental rollout)
- Industry standard (LangChain best practice)
- 2-3 hours effort
- Immediate ROI (reduced debugging time)

**When to implement:** After current architecture documentation is complete

**Owner:** TBD

**Target Date:** TBD
