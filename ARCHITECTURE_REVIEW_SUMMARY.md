# Architecture Review Summary

## 📚 Documentation Structure

We now have three key documents:

1. **`API_REVIEW.md`** - Deep dive on DI & Configuration issues
2. **`IMPLEMENTATION_PLAN.md`** - Complete implementation roadmap (THIS IS THE MASTER PLAN)
3. This summary document

---

## 🎯 Three Critical Design Decisions

### 1. **CIF_NO as API State (Not User Input)**

**Why:** Eliminate ambiguity and extraction errors

**Change:**
```python
# BEFORE: User must type CIF in query
POST /api/query
{
  "query": "What is the risk score for customer C000001?"
}
# Agent extracts C000001 with regex - error prone!

# AFTER: CIF is known context from UI
POST /api/query
{
  "query": "What is the risk score?",
  "context": {
    "cif_no": "C000001"  # UI already knows this!
  }
}
```

**Benefits:**
- ✅ No extraction errors
- ✅ User doesn't repeat CIF every query
- ✅ API can enforce access control
- ✅ Supports multi-entity queries
- ✅ Better UX

**Implementation Priority:** 🔴 HIGH (Sprint 2)

---

### 2. **Materialize Feature → Red Flag → Typology Mapping**

**Why:** Systematic, auditable, explainable typology detection

**Change:**
```python
# BEFORE: Compliance expert guesses typologies from data
"This customer has 15 cash transactions, might be structuring..."

# AFTER: Systematic mapping with evidence
{
  "typology": "structuring",
  "confidence": 0.85,
  "red_flags": [
    {
      "feature": "count_cash_intensive_txn_w0_90",
      "value": 15,
      "threshold": ">10",
      "severity": "high"
    }
  ],
  "regulatory_references": ["FATF Recommendation 10"]
}
```

**Approach:**
1. Create `data/typology_mappings.json` - source of truth
2. Create `TypologyService` - analyzes features systematically
3. Integrate with compliance expert - provide evidence-based analysis

**Benefits:**
- ✅ Consistent typology detection
- ✅ Explainable (show exact red flags)
- ✅ Auditable trail
- ✅ Testable & maintainable
- ✅ No hallucinations

**Implementation Priority:** 🟡 MEDIUM (Sprint 3)

---

### 3. **Review Loop for Agent Responses**

**Why:** Safety, compliance, audit trail

**Change:**
```python
# BEFORE: Agent response goes directly to user
Agent generates response → Return to user

# AFTER: Multi-stage review
Agent generates response → Self-review → Decision
                                            ↓
                                  ┌─────────┴─────────┐
                              Low Risk            High Risk
                                  ↓                   ↓
                          Auto-approve      Store for human review
                                  ↓                   ↓
                              User sees        Reviewer approves
                              immediately        before showing
```

**Levels:**
1. **Self-Review (Automated)** - Agent checks its own work
   - Hallucination detection
   - Completeness check
   - Confidence scoring

2. **Human Review (Conditional)** - Based on risk
   - SAR/STR recommendations → Always review
   - High-risk typologies → Always review
   - PEP/Sanctions → Always review
   - Low-risk queries → Auto-approve

**Benefits:**
- ✅ Prevents hallucinations from reaching users
- ✅ Compliance safety net for critical decisions
- ✅ Complete audit trail
- ✅ Feedback loop for agent improvement
- ✅ Regulatory compliance

**Implementation Priority:** 🟡 MEDIUM (Sprint 4-5)

---

## 🏗️ Architecture Changes

### Current State
```
API → AMLCopilot() → Graph → Agents (hardcoded models, extract CIF, no review)
                                ↓
                         Direct response
```

### Future State
```
API (with context) → AMLCopilot(config) → Graph (DI) → Agents (configured models)
                                                            ↓
Settings (.env) → AgentConfig → Coordinator (gpt-4o-mini)
                              → Intent Mapper (uses context, no extraction)
                              → Data Retrieval + Typology Service
                              → Compliance Expert (evidence-based)
                              → Self-Review
                                   ↓
                         ┌─────────┴─────────┐
                    Auto-approve      Needs Review → Storage
                         ↓                             ↓
                      Response              Review API → Human
```

---

## 📋 Implementation Phases

### **Phase 1: DI & Configuration** (Week 1) 🔴 CRITICAL
**Why first:** Everything depends on this

- Create `AgentConfig` models
- Update all agents to accept config
- Update API to pass configuration
- Validate we can change models via .env

**Blocker:** Nothing can proceed without this

---

### **Phase 2: Context-Aware Queries** (Week 2) 🔴 HIGH
**Why second:** Simplifies everything downstream

- Add `context` to API requests
- Update state to include context
- Update agents to use context (no CIF extraction!)
- Simplify intent mapper significantly

**Benefits:** Cleaner code, fewer bugs, better UX

---

### **Phase 3: Typology Mapping** (Week 3) 🟡 MEDIUM
**Why third:** Can be developed in parallel with Phase 2

- Create typology mappings JSON
- Create TypologyService
- Integrate with data retrieval
- Update compliance expert

**Benefits:** Better analysis, explainability, compliance

---

### **Phase 4: Review System** (Weeks 4-5) 🟡 MEDIUM
**Why later:** Requires Phases 1-3 to be solid

- Create review models & storage
- Implement self-review logic
- Add review nodes to graph
- Create review API endpoints
- Build reviewer UI

**Benefits:** Safety, compliance, audit trail

---

### **Phase 5+: Enhancements** (Ongoing) 🟢 NICE-TO-HAVE

- Session management
- Multi-entity queries
- Async processing
- Monitoring & observability

---

## 🎯 Immediate Next Steps

### If starting from scratch:
1. ✅ Review complete (you are here)
2. Start Phase 1: Create `config/agent_config.py`
3. Continue Phase 1: Update agents for DI

### Recommended first PR:
**Title:** "Phase 1: Implement Dependency Injection for Agent Configuration"

**Files changed:**
- `config/agent_config.py` (new)
- `config/settings.py` (update)
- `agents/coordinator.py` (update __init__)
- `agents/intent_mapper.py` (update __init__)
- `agents/data_retrieval.py` (update __init__)
- `agents/compliance_expert.py` (update __init__)
- `agents/graph.py` (update AMLCopilot, graph creation)
- `api/main.py` (update lifespan)
- `.env.example` (new)
- Tests

**Test plan:**
- Unit tests for each agent with mock configs
- Integration test that config propagates correctly
- Test changing models via environment variables

---

## 🤔 Open Questions

### 1. Session Storage
**Question:** Redis or database for sessions?
**Options:**
- Redis (fast, temporary)
- PostgreSQL (persistent, queryable)
- Hybrid (Redis for hot, DB for history)

**Recommendation:** Start with PostgreSQL for simplicity, move to hybrid later

### 2. Review Queue Priority
**Question:** How to prioritize review queue?
**Options:**
- FIFO
- Risk-based (high risk first)
- User-based (VIP customers first)
- SLA-based (approaching deadline first)

**Recommendation:** Risk-based with SLA fallback

### 3. Async vs Sync
**Question:** Should all endpoints be async?
**Current:** Sync
**Future:** Most queries < 5 seconds, probably fine sync for MVP

**Recommendation:** Start sync, add async for specific slow queries

### 4. Typology Confidence Scoring
**Question:** How to calculate confidence for typology matches?
**Options:**
- Binary (matches or not)
- Rule-based (number of red flags)
- ML-based (train on historical data)

**Recommendation:** Start rule-based, enhance with ML later

---

## 📊 Success Criteria

After all phases complete, we should have:

### Configuration
- ✅ Change LLM models via `.env`
- ✅ Different configs per environment
- ✅ No hardcoded model names in code

### Context Handling
- ✅ Zero CIF extraction errors
- ✅ Users don't type CIF repeatedly
- ✅ Support multi-entity queries

### Typology Detection
- ✅ >90% precision on known typologies
- ✅ Clear audit trail (feature → red flag → typology)
- ✅ No ad-hoc typology guessing

### Review System
- ✅ <10% queries need human review
- ✅ Zero hallucinations reach users
- ✅ Complete audit trail
- ✅ <5 min average review time

### Quality
- ✅ >90% test coverage
- ✅ <2 second average response time
- ✅ Comprehensive documentation

---

## 🚦 Go/No-Go for Production

Before production deployment, verify:

- [ ] All Phase 1 (DI) complete and tested
- [ ] All Phase 2 (Context) complete and tested
- [ ] Phase 3 (Typology) at least 80% complete
- [ ] Phase 4 (Review) for high-risk queries implemented
- [ ] Load testing passed (1000 concurrent users)
- [ ] Security audit passed
- [ ] Documentation complete
- [ ] Runbooks prepared
- [ ] Monitoring & alerting configured
- [ ] Rollback plan tested

---

## 📞 Support During Implementation

When implementing, refer to:

- **DI Issues** → `API_REVIEW.md`
- **Overall Plan** → `IMPLEMENTATION_PLAN.md`
- **Architecture** → `ARCHITECTURE.md`
- **Business Context** → `objective.md`

---

## 💡 Key Insights from Review

1. **The hardcoded models issue is critical** - Blocks any production use
2. **CIF extraction is fragile** - Will cause user frustration
3. **Typology detection is ad-hoc** - Not auditable for compliance
4. **No safety net** - Hallucinations go straight to users
5. **Good foundation** - Architecture is sound, just needs these fixes

**The good news:** All issues are fixable with clear implementation path!

---

## ✅ Ready to Proceed?

You now have:
- ✅ Complete understanding of current state
- ✅ Three critical design decisions documented
- ✅ Full implementation plan with 6-phase roadmap
- ✅ Prioritized checklist with ~80 tasks
- ✅ Success criteria and go/no-go checklist

**Next:** Would you like me to start implementing Phase 1 (DI & Configuration)?
