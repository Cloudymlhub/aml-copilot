# API Testing Setup - Summary

**Date:** November 17, 2025
**Task:** Create comprehensive API testing infrastructure

---

## ✅ What Was Created

### 1. **Comprehensive Testing Notebook** 📓
**File:** `notebooks/api_testing.ipynb`

A fully-featured Jupyter notebook with:
- ✅ Setup and helper functions
- ✅ Health checks
- ✅ All API endpoint tests
- ✅ Basic customer queries
- ✅ Risk assessment tests
- ✅ Transaction pattern analysis
- ✅ Session continuity testing
- ✅ Out-of-scope query handling
- ✅ Ambiguous query testing (PEAR loop)
- ✅ Alert-based investigations
- ✅ Cache management
- ✅ Batch processing (multiple customers)
- ✅ Performance benchmarking
- ✅ Pretty-formatted outputs with JSON, Markdown, and DataFrames

**Tests 11 different scenarios across 12+ test cells!**

### 2. **Notebook Documentation** 📚
**File:** `notebooks/README.md`

Complete guide including:
- Getting started instructions
- Cell-by-cell walkthrough
- Common use cases with code examples
- Customization guide
- Troubleshooting section
- Expected results and sample outputs
- Learning path (beginner → advanced)
- Tips and best practices

### 3. **Dependencies Updated** 📦
**File:** `pyproject.toml`

Added testing dependencies:
```toml
"jupyter (>=1.0.0,<2.0.0)",
"pandas (>=2.0.0,<3.0.0)",
"requests (>=2.31.0,<3.0.0)"
```

### 4. **Makefile Commands** 🔧
**File:** `Makefile`

New commands added:
```bash
make notebook       # Start Jupyter Notebook server
make notebook-lab   # Start Jupyter Lab server
```

### 5. **Quick Start Guide** 🚀
**File:** `QUICK_START.md`

Complete getting-started guide with:
- Super quick start (5 commands)
- Detailed step-by-step instructions
- Sample queries to try
- Development workflows
- Troubleshooting guide
- Next steps and learning path
- Success checklist

### 6. **Updated Cheat Sheet** 📋
**File:** `.make-cheatsheet`

Added:
- Notebook commands
- Testing workflow examples

---

## 🎯 How to Use

### Option 1: Interactive Notebook (Recommended)

**Terminal 1: Start API**
```bash
make api-run
```

**Terminal 2: Start Notebook**
```bash
make notebook
```

**Then:**
1. Open http://localhost:8888
2. Navigate to `notebooks/api_testing.ipynb`
3. Run: `Kernel > Restart & Run All`
4. Explore results!

### Option 2: API Interactive Docs

1. Start API: `make api-run`
2. Open: http://localhost:8000/docs
3. Try endpoints interactively

### Option 3: cURL Commands

```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the customer'\''s risk score?",
    "context": {"cif_no": "C000001"},
    "user_id": "analyst_1",
    "session_id": "test_1"
  }'
```

---

## 📊 What Can Be Tested

### API Endpoints Covered

| Endpoint | Method | Purpose | Notebook Cell |
|----------|--------|---------|---------------|
| `/health` | GET | Health check | Cell 2 |
| `/api/tools` | GET | List available tools | Cell 3 |
| `/api/query` | POST | Query copilot | Cells 4-9 |
| `/api/sessions/{user}/{session}/history` | GET | Get conversation history | Cell 7 |
| `/api/sessions/{user}/{session}` | GET | Get session info | - |
| `/api/sessions/{user}/{session}` | DELETE | Clear session | Cell 7 |
| `/api/cache/clear` | POST | Clear Redis cache | Cell 10 |

### Query Types Tested

1. **Basic Data Queries**
   - Customer basic information
   - Risk scores and levels
   - KYC status

2. **Complex Analysis**
   - Transaction patterns
   - AML typology detection
   - Full risk assessments

3. **Conceptual Questions**
   - "What is structuring?"
   - Compliance guidance
   - Regulatory information

4. **Session-Based**
   - Multi-turn conversations
   - Context preservation
   - Follow-up questions

5. **Edge Cases**
   - Out-of-scope queries
   - Ambiguous questions
   - Missing data scenarios

---

## 🔍 Test Coverage

### Agents Tested

- ✅ **Coordinator** - Routing and scope validation
- ✅ **Intent Mapper** - Tool selection (via bind_tools)
- ✅ **Data Retrieval** - Database queries
- ✅ **Compliance Expert** - AML analysis
- ✅ **Review Agent** - Quality assurance (PEAR loop)

### Features Tested

- ✅ Multi-agent orchestration
- ✅ Session persistence (Redis checkpoints)
- ✅ Data caching (Redis)
- ✅ Tool execution
- ✅ Natural language understanding
- ✅ Compliance analysis
- ✅ Replanning (needs_data, needs_refinement)
- ✅ Error handling
- ✅ Response formatting

---

## 📈 Performance Benchmarks

The notebook includes performance testing (Cell 12):
- Measures response time per query type
- Compares different query complexities
- Calculates average response times
- Identifies bottlenecks

**Expected Results:**
- Simple queries: 1-3 seconds
- Complex analysis: 3-7 seconds
- Conceptual questions: 2-4 seconds

---

## 🎓 Learning Flow

### For New Users

1. **Read:** `QUICK_START.md` (5 min)
2. **Setup:** `make setup` (2 min)
3. **Run:** `make api-run` (keep running)
4. **Test:** `make notebook` → run all cells (5 min)
5. **Explore:** Try custom queries

**Total time:** ~15 minutes to full understanding

### For Developers

1. **Architecture:** `ARCHITECTURE.md`
2. **Configuration:** `ENV_CONFIGURATION_GUIDE.md`
3. **Testing:** Run full notebook
4. **Customize:** Add your own test cells
5. **Integrate:** Build your frontend

---

## 🔧 Installation Steps

```bash
# 1. Install new dependencies
make install

# This installs:
# - jupyter (notebook interface)
# - pandas (data analysis)
# - requests (HTTP client)
# Already had: fastapi, uvicorn

# 2. Verify installation
poetry run jupyter --version
```

---

## 📝 Example Test Scenarios

### Scenario 1: New Customer Investigation

```python
session_id = "investigation_new_customer"

# Step 1: Get basic info
query_copilot("Get basic customer information", "C000005", session_id=session_id)

# Step 2: Check risk
query_copilot("What is the risk assessment?", "C000005", session_id=session_id)

# Step 3: Analyze transactions
query_copilot("Show transaction patterns", "C000005", session_id=session_id)

# Step 4: Get recommendations
query_copilot("What actions should I take?", "C000005", session_id=session_id)

# View full history
requests.get(f"{BASE_URL}/api/sessions/analyst_1/{session_id}/history")
```

### Scenario 2: Alert Response

```python
payload = {
    "query": "Investigate this high-risk transaction alert",
    "context": {
        "cif_no": "C000007",
        "alert_id": "ALT001"
    },
    "user_id": "analyst_jane",
    "session_id": "alert_response_001"
}

response = requests.post(f"{BASE_URL}/api/query", json=payload)
result = response.json()

# Analyze compliance insights
if result.get('compliance_analysis'):
    print("Risk:", result['compliance_analysis']['risk_assessment'])
    print("Typologies:", result['compliance_analysis']['typologies'])
    print("Recommendations:", result['compliance_analysis']['recommendations'])
```

### Scenario 3: Batch Risk Review

```python
high_risk_customers = ["C000008", "C000009", "C000010"]
results = []

for cif in high_risk_customers:
    result = query_copilot(
        "Provide full AML risk assessment with recommendations",
        cif
    )

    if result.get('compliance_analysis'):
        results.append({
            'CIF': cif,
            'Risk': result['compliance_analysis'].get('risk_assessment'),
            'Typologies': ', '.join(result['compliance_analysis'].get('typologies', [])),
            'Actions': len(result['compliance_analysis'].get('recommendations', []))
        })

# Create summary report
df = pd.DataFrame(results)
display(df)
```

---

## 🐛 Common Issues & Solutions

### Issue 1: Notebook won't start

**Error:** `jupyter: command not found`

**Solution:**
```bash
make install
poetry run jupyter --version  # Verify
```

### Issue 2: API connection refused

**Error:** Connection refused to localhost:8000

**Solution:**
```bash
# Terminal 1: Make sure API is running
make api-run

# Terminal 2: Then start notebook
make notebook
```

### Issue 3: Empty responses

**Error:** Retrieved data is null/empty

**Solution:**
```bash
# Database might not be seeded
make db-seed

# Or use valid customer IDs: C000001-C000010
```

### Issue 4: Slow responses

**Possible causes:**
- OpenAI API latency
- Database not indexed
- Cache not working

**Check:**
```bash
make status           # Verify all services healthy
make redis-info       # Check cache usage
```

---

## 🎯 Success Indicators

**✅ Setup is correct if:**

1. Health check returns all "healthy"
2. First query completes in < 10 seconds
3. Compliance analysis is present in responses
4. Session history persists between queries
5. Performance test shows reasonable times

**Sample successful output:**
```json
{
  "response": "Customer C000001 has a risk score of 27.15...",
  "session_id": "test_session",
  "compliance_analysis": {
    "analysis": "Low risk customer...",
    "risk_assessment": "LOW",
    "recommendations": ["Continue monitoring"]
  },
  "retrieved_data": { ... }
}
```

---

## 📚 Documentation Hierarchy

```
QUICK_START.md              ← Start here!
├── How to setup
├── How to test (3 options)
└── Troubleshooting

notebooks/README.md         ← Notebook guide
├── Cell-by-cell walkthrough
├── Use cases
└── Customization

MAKEFILE_GUIDE.md          ← Command reference
├── All make commands
├── Workflows
└── Examples

ENV_CONFIGURATION_GUIDE.md  ← Configuration
├── Agent models
├── Timeouts
└── Cost optimization

ARCHITECTURE.md            ← System design
├── Multi-agent system
├── PEAR pattern
└── State management
```

---

## 🚀 Next Actions

### Immediate (Today)

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Test the notebook:**
   ```bash
   # Terminal 1
   make api-run

   # Terminal 2
   make notebook
   ```

3. **Run all test cells** in `api_testing.ipynb`

### Short Term (This Week)

1. Customize notebook for your use cases
2. Create additional test scenarios
3. Build visualization dashboards
4. Document API integration patterns

### Long Term (Production)

1. Set up automated testing pipeline
2. Create performance benchmarks
3. Build frontend integration
4. Add authentication/authorization

---

## 💡 Pro Tips

1. **Keep three terminals open:**
   - Terminal 1: `make api-run` (API server)
   - Terminal 2: `make notebook` (testing)
   - Terminal 3: `make services-logs` (monitoring)

2. **Use consistent session IDs** for related queries to preserve context

3. **Clear cache** (`make redis-flush`) when testing data changes

4. **Save interesting sessions** by noting session IDs for later review

5. **Export notebook results** as HTML for documentation:
   ```bash
   jupyter nbconvert --to html notebooks/api_testing.ipynb
   ```

---

## ✅ Verification Checklist

- [x] Jupyter notebook created (`notebooks/api_testing.ipynb`)
- [x] Notebook README created (`notebooks/README.md`)
- [x] Dependencies added to `pyproject.toml`
- [x] Makefile commands added (`make notebook`, `make notebook-lab`)
- [x] Quick start guide created (`QUICK_START.md`)
- [x] Cheat sheet updated (`.make-cheatsheet`)
- [x] All 11 test scenarios implemented
- [x] Helper functions for easy testing
- [x] Performance benchmarking included
- [x] Documentation cross-references added

---

**🎉 Complete testing infrastructure ready!**

Start testing with: `make notebook`

For questions, see `QUICK_START.md` or `notebooks/README.md`
