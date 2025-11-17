# AML Copilot Testing Notebooks

This directory contains Jupyter notebooks for interactive API testing and exploration.

## 📚 Available Notebooks

### `api_testing.ipynb` - Comprehensive API Testing

A complete test suite for the AML Copilot API covering:
- ✅ Health checks and system status
- ✅ Basic customer queries
- ✅ Risk assessment and compliance analysis
- ✅ Transaction pattern analysis
- ✅ Session continuity and conversation history
- ✅ Out-of-scope query handling
- ✅ Ambiguous query testing (PEAR loop)
- ✅ Alert-based investigations
- ✅ Cache management
- ✅ Batch processing multiple customers
- ✅ Performance benchmarking

## 🚀 Getting Started

### Prerequisites

**1. Install dependencies:**
```bash
make install
```

**2. Start services:**
```bash
make services-start
```

**3. Prepare database:**
```bash
make db-migrate
make db-seed
```

**4. Start the API:**
```bash
make api-run
```
Keep this running in a separate terminal.

### Running the Notebook

**Option 1: Classic Jupyter Notebook**
```bash
make notebook
```
Opens at: http://localhost:8888

**Option 2: Jupyter Lab (Recommended)**
```bash
make notebook-lab
```
Opens at: http://localhost:8888

**Option 3: Direct Command**
```bash
cd notebooks
poetry run jupyter notebook
```

## 📝 Using the Testing Notebook

### Quick Test Flow

1. **Open `api_testing.ipynb`**
2. **Run all cells**: `Kernel > Restart & Run All`
3. **Review results**: Scroll through to see test results
4. **Customize**: Modify queries and customer IDs as needed

### Cell-by-Cell Execution

For detailed exploration:
1. Run cells sequentially from top to bottom
2. Each section tests a different aspect of the API
3. Outputs are formatted with:
   - 📊 JSON responses
   - 🎯 Compliance analysis
   - 📋 Data tables
   - ⏱️ Performance metrics

### Key Sections

#### 1. Setup (Cells 1-2)
- Imports and helper functions
- Health check

#### 2. Basic Tests (Cells 3-5)
- Simple queries to get started
- Customer info, risk scores, transaction patterns

#### 3. Advanced Tests (Cells 6-9)
- Session continuity
- Out-of-scope handling
- Alert investigations

#### 4. System Tests (Cells 10-11)
- Cache management
- Batch processing

#### 5. Performance (Cell 12)
- Response time measurement
- Query type comparisons

## 🎯 Common Use Cases

### Test a Specific Customer

```python
result = query_copilot(
    query="Analyze this customer for AML risk",
    cif_no="C000001"
)
```

### Test Session Continuity

```python
session_id = "my_test_session"
user_id = "analyst_1"

# Query 1
query_copilot("Get basic info", "C000001", user_id, session_id)

# Query 2 - uses context from Query 1
query_copilot("What is their risk score?", "C000001", user_id, session_id)

# View history
requests.get(f"{BASE_URL}/api/sessions/{user_id}/{session_id}/history")
```

### Test Multiple Customers

```python
customers = ["C000001", "C000002", "C000003"]
for cif in customers:
    result = query_copilot("Get risk assessment", cif)
    # Process result...
```

### Performance Testing

```python
import time

start = time.time()
result = query_copilot("Your query here", "C000001")
elapsed = time.time() - start

print(f"Response time: {elapsed:.2f} seconds")
```

## 🔧 Customization

### Create Your Own Test Cells

Add new cells to test specific scenarios:

```python
# Test specific AML typology
result = query_copilot(
    query="Check for structuring patterns in the last 30 days",
    cif_no="C000005"
)

# Test with alert context
payload = {
    "query": "Investigate this alert",
    "context": {
        "cif_no": "C000001",
        "alert_id": "ALT123"
    },
    "user_id": "analyst_1",
    "session_id": "alert_investigation_1"
}
response = requests.post(f"{BASE_URL}/api/query", json=payload)
```

### Visualize Results

```python
import pandas as pd
import matplotlib.pyplot as plt

# Extract risk scores from batch test
risk_scores = [result['risk_score'] for result in batch_results]
cif_numbers = [result['cif_no'] for result in batch_results]

# Plot
plt.bar(cif_numbers, risk_scores)
plt.xlabel('Customer')
plt.ylabel('Risk Score')
plt.title('Customer Risk Scores')
plt.show()
```

## 🐛 Troubleshooting

### "Connection refused" errors

**Problem:** API not running

**Solution:**
```bash
# Check API status
curl http://localhost:8000/health

# If not running, start it:
make api-run
```

### "No module named 'jupyter'"

**Problem:** Dependencies not installed

**Solution:**
```bash
make install
```

### Notebook kernel crashes

**Problem:** API might be down or database not seeded

**Solution:**
```bash
make status          # Check all services
make db-seed         # Ensure data is loaded
make api-run         # Restart API
```

### Empty or error responses

**Problem:** Database might be empty

**Solution:**
```bash
make db-refresh      # Reset and seed database
```

## 📊 Expected Results

### Healthy System
- Health check: All components show "healthy"
- Query responses: < 5 seconds for most queries
- Retrieved data: Non-empty for valid customer IDs
- Compliance analysis: Present for data queries

### Sample Output
```json
{
  "response": "Customer C000001 has a risk score of 27.15 (LOW risk)...",
  "session_id": "test_session_20250117",
  "compliance_analysis": {
    "analysis": "Customer presents low AML risk based on...",
    "risk_assessment": "LOW",
    "typologies": [],
    "recommendations": ["Continue standard monitoring"],
    "regulatory_references": ["FATF Recommendation 10"]
  },
  "retrieved_data": {
    "customer_name": "John Doe",
    "risk_score": 27.15,
    "risk_level": "LOW"
  }
}
```

## 📚 Additional Resources

- **API Documentation:** http://localhost:8000/docs
- **Architecture Guide:** `../ARCHITECTURE.md`
- **Configuration Guide:** `../ENV_CONFIGURATION_GUIDE.md`
- **Makefile Guide:** `../MAKEFILE_GUIDE.md`

## 🎓 Learning Path

### Beginner
1. Run the full notebook end-to-end
2. Observe different response types
3. Try modifying customer IDs

### Intermediate
1. Create custom queries
2. Test edge cases
3. Explore session management

### Advanced
1. Performance optimization testing
2. Load testing with concurrent requests
3. Integration with your own frontend

## 💡 Tips

1. **Keep API logs visible:** Run `make services-logs` in another terminal
2. **Clear cache between tests:** Use the cache clear cell
3. **Save session IDs:** Track interesting sessions for later review
4. **Export results:** Save DataFrames to CSV for reporting
5. **Use markdown cells:** Document your custom tests

## 🚀 Next Steps

After testing the API:
1. Integrate with your frontend application
2. Set up automated testing pipeline
3. Create custom notebooks for specific workflows
4. Build visualization dashboards

---

**Happy Testing! 🎉**

For issues or questions, refer to the main project documentation or check the API logs.
