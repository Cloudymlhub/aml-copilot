# Implementation Checklist - Agent Architecture

## ✅ Phase 1: Infrastructure (COMPLETE)

### Core Components
- [x] **agents/state.py**
  - [x] Removed `MessageAccessLevel` enum
  - [x] Added `AgentResponse` TypedDict with all state update fields
  - [x] Updated `get_conversation_context()` to use `Optional[int]`
  - [x] Pattern: `None`=ALL, `0`=NONE, `N`=last N messages

- [x] **agents/base_agent.py**
  - [x] Abstract base class with `__call__() -> AgentResponse`
  - [x] `get_messages()` method using `message_history_limit`
  - [x] Helper methods: `_create_agent_message()`, `_append_message()`, `log_agent_start()`
  - [x] Updated to use `Optional[int]` instead of enum

- [x] **config/agent_config.py**
  - [x] Replaced `message_access_level: MessageAccessLevel` 
  - [x] Added `message_history_limit: Optional[int] = 0`
  - [x] Updated example in docstring

- [x] **config/settings.py**
  - [x] Coordinator: `message_history_limit=3`
  - [x] Intent Mapper: `message_history_limit=10`
  - [x] Compliance Expert: `message_history_limit=None`
  - [x] Review Expert: `message_history_limit=None`

- [x] **agents/__init__.py**
  - [x] Export `AgentResponse`
  - [x] Export `BaseAgent`
  - [x] Export `get_conversation_context`
  - [x] Removed `MessageAccessLevel` export

### Documentation
- [x] **docs/AGENT_ARCHITECTURE_REVISED.md**
  - [x] Complete design rationale
  - [x] Optional[int] vs Enum comparison
  - [x] AgentResponse benefits
  - [x] Migration patterns
  - [x] Configuration matrix
  - [x] Examples and quick reference

## 🔄 Phase 2: Agent Refactoring (TODO)

### Priority 1: Coordinator Agent
- [ ] **agents/subagents/coordinator.py**
  - [ ] Import: `from agents.base_agent import BaseAgent`
  - [ ] Import: `from agents.state import AgentResponse`
  - [ ] Inherit: `class CoordinatorAgent(BaseAgent):`
  - [ ] Update `__init__()`: Call `super().__init__(config)`
  - [ ] Update `__call__()`: Return type `-> AgentResponse`
  - [ ] Add: `self.log_agent_start(state)` at beginning
  - [ ] Replace direct message access with: `messages = self.get_messages(state)`
  - [ ] Use: `self._append_message()` for message updates
  - [ ] Verify config: `message_history_limit=3` is set

### Priority 2: Intent Mapper Agent
- [ ] **agents/subagents/intent_mapper.py**
  - [ ] Import: `from agents.base_agent import BaseAgent`
  - [ ] Import: `from agents.state import AgentResponse`
  - [ ] Inherit: `class IntentMappingAgent(BaseAgent):`
  - [ ] Update `__init__()`: Call `super().__init__(config)`
  - [ ] Update `__call__()`: Return type `-> AgentResponse`
  - [ ] Add: `self.log_agent_start(state)` at beginning
  - [ ] Replace manual message list creation with: `messages = self.get_messages(state)`
  - [ ] Update LLM invocation to use conversation context
  - [ ] Use: `self._append_message()` for message updates
  - [ ] Verify config: `message_history_limit=10` is set

### Priority 3: Compliance Expert Agent
- [ ] **agents/subagents/compliance_expert.py**
  - [ ] Import: `from agents.base_agent import BaseAgent`
  - [ ] Import: `from agents.state import AgentResponse`
  - [ ] Inherit: `class ComplianceExpertAgent(BaseAgent):`
  - [ ] Update `__init__()`: Call `super().__init__(config)`
  - [ ] Update `__call__()`: Return type `-> AgentResponse`
  - [ ] Add: `self.log_agent_start(state)` at beginning
  - [ ] Replace: `user_query` only with `messages = self.get_messages(state)`
  - [ ] Pass ALL messages to LLM for comprehensive context
  - [ ] Use: `self._append_message()` for message updates
  - [ ] Verify config: `message_history_limit=None` is set

### Priority 4: Review Agent
- [ ] **agents/subagents/review_agent.py**
  - [ ] Import: `from agents.base_agent import BaseAgent`
  - [ ] Import: `from agents.state import AgentResponse`
  - [ ] Inherit: `class ReviewAgent(BaseAgent):`
  - [ ] Update `__init__()`: Call `super().__init__(config)`
  - [ ] Update `__call__()`: Return type `-> AgentResponse`
  - [ ] Add: `self.log_agent_start(state)` at beginning
  - [ ] Add: `messages = self.get_messages(state)` for full context
  - [ ] Include conversation history in review analysis
  - [ ] Use: `self._append_message()` for message updates
  - [ ] Verify config: `message_history_limit=None` is set

### Priority 5: Data Retrieval Agent
- [ ] **agents/subagents/data_retrieval.py**
  - [ ] Import: `from agents.base_agent import BaseAgent`
  - [ ] Import: `from agents.state import AgentResponse`
  - [ ] Inherit: `class DataRetrievalAgent(BaseAgent):`
  - [ ] Update `__init__()`: Accept `config: AgentConfig` parameter
  - [ ] Call: `super().__init__(config)`
  - [ ] Update `__call__()`: Return type `-> AgentResponse`
  - [ ] Add: `self.log_agent_start(state)` at beginning
  - [ ] Note: No need to call `get_messages()` - pure executor with `limit=0`
  - [ ] Use: `self._append_message()` for message updates
  - [ ] Add config in settings.py (currently doesn't have one)

### Priority 6: Graph Updates
- [ ] **agents/graph.py**
  - [ ] Verify: All agents receive their configs properly
  - [ ] Verify: DataRetrievalAgent now accepts config parameter
  - [ ] Test: Agent initialization works with new patterns

## 🧪 Phase 3: Testing (TODO)

### Unit Tests
- [ ] **tests/test_message_access.py** (new file)
  - [ ] Test `get_conversation_context()` with `None` (returns all)
  - [ ] Test `get_conversation_context()` with `0` (returns empty)
  - [ ] Test `get_conversation_context()` with `N` (returns last N)
  - [ ] Test edge cases: negative numbers, N > len(messages)

- [ ] **tests/test_base_agent.py** (new file)
  - [ ] Test BaseAgent initialization
  - [ ] Test `get_messages()` respects config
  - [ ] Test helper methods: `_create_agent_message()`, `_append_message()`
  - [ ] Test `log_agent_start()` logs correctly

- [ ] **tests/test_agent_integration.py** (new file)
  - [ ] Test each refactored agent uses correct history limit
  - [ ] Test Coordinator gets 3 messages
  - [ ] Test Intent Mapper gets 10 messages
  - [ ] Test Compliance Expert gets ALL messages
  - [ ] Test Review Agent gets ALL messages
  - [ ] Test Data Retrieval gets NO messages

### Integration Tests
- [ ] **Test conversation continuity**
  - [ ] Multi-turn conversation: "Show customer X" → "What about their transactions?"
  - [ ] Verify Intent Mapper resolves "their" correctly
  - [ ] Verify context propagates through state

- [ ] **Test reference resolution**
  - [ ] Query: "Tell me about customer 12345"
  - [ ] Follow-up: "Show me that customer's high-risk transactions"
  - [ ] Verify "that customer" resolves to 12345

- [ ] **Test checkpointing integration**
  - [ ] Create session, run query
  - [ ] Continue session with follow-up
  - [ ] Verify messages array contains full history
  - [ ] Verify agents get correct slice based on limit

## 📊 Validation Checklist

### Code Quality
- [ ] No `state["messages"]` direct access in agent code (use `get_messages()`)
- [ ] All agents inherit from `BaseAgent`
- [ ] All `__call__()` methods return `AgentResponse`
- [ ] All agents use `self._append_message()` helper
- [ ] All agents call `self.log_agent_start(state)`
- [ ] Type hints are correct throughout

### Configuration
- [ ] Coordinator: `message_history_limit=3` ✅
- [ ] Intent Mapper: `message_history_limit=10` ✅
- [ ] Data Retrieval: `message_history_limit=0` ⏳
- [ ] Compliance Expert: `message_history_limit=None` ✅
- [ ] Review Agent: `message_history_limit=None` ✅

### Documentation
- [ ] Update `ARCHITECTURE.md` with new patterns
- [ ] Update agent docstrings with history limit info
- [ ] Add examples to documentation
- [ ] Update API documentation if needed

### Testing
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing: multi-turn conversations work
- [ ] Manual testing: reference resolution works
- [ ] No regression in existing functionality

## 🎯 Success Criteria

### Functional
- ✅ Agents can declare their history needs via config
- ✅ Configuration uses intuitive `Optional[int]` pattern
- ✅ Type-safe return values via `AgentResponse`
- ⏳ Conversation continuity works correctly
- ⏳ Reference resolution works ("their", "that customer")
- ⏳ Multi-turn conversations maintain context

### Technical
- ✅ Clean, consistent interface across all agents
- ✅ Centralized message access logic
- ✅ Type hints throughout
- ⏳ 90%+ test coverage on new code
- ⏳ No breaking changes to existing API

### Documentation
- ✅ Clear examples and rationale
- ✅ Migration guide for each agent
- ✅ Configuration reference
- ⏳ Updated architecture docs

## 📝 Notes

### Design Decisions Made
1. **Optional[int] over Enum**: More flexible and intuitive
2. **AgentResponse TypedDict**: Better type safety for returns
3. **total=False**: Agents only return fields they update
4. **Default limit=0**: Safe default (no history)
5. **None means ALL**: Natural interpretation

### Remaining Questions
1. Should DataRetrievalAgent use config? **Yes - for consistency**
2. Can history limit change per query? **No - static per agent (for now)**
3. Should we add validation (e.g., limit must be >= 0)? **Handled in helper function**

### Breaking Changes
- Agents must now inherit from BaseAgent (migration required)
- Config field renamed: `message_access_level` → `message_history_limit`
- Import changed: No more `MessageAccessLevel` enum
- Return type changed: `Dict[str, Any]` → `AgentResponse`

### Migration Strategy
- ✅ Phase 1: Build infrastructure (COMPLETE)
- 🔄 Phase 2: Refactor agents one-by-one (IN PROGRESS)
- ⏳ Phase 3: Add comprehensive tests
- ⏳ Phase 4: Update documentation
- ⏳ Phase 5: Production deployment

## 🚀 Next Steps

**Immediate (Right Now):**
1. Review the revised design
2. Confirm the approach (Optional[int] + AgentResponse)
3. Choose first agent to refactor (recommend: Coordinator)

**Short Term (This Session):**
1. Refactor Coordinator agent
2. Test basic conversation continuity
3. Refactor Intent Mapper agent
4. Test reference resolution

**Medium Term (Next Session):**
1. Refactor remaining agents
2. Add comprehensive test suite
3. Update all documentation
4. Manual testing with real queries

---

**Status**: Phase 1 complete ✅ | Phase 2 ready to start 🔄 | Infrastructure solid 💪
