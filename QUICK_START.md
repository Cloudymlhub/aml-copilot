# 🚀 AML Copilot - Quick Start Guide

Get up and running with the AML Copilot API in 5 minutes!

## ⚡ Super Quick Start

```bash
# 1. Install dependencies
make install

# 2. Set your OpenAI API key in .env
# Edit .env and replace: OPENAI_API_KEY=your-key-here

# 3. Setup everything (services + database)
make setup

# 4. Run the API
make api-run

# 5. Test the API (in another terminal)
make notebook
```

**Done!**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Notebook: http://localhost:8888

---

## 📋 Detailed Steps

### Step 1: Prerequisites

**Required:**
- Python 3.11+
- Poetry (Python dependency manager)
- Docker & Docker Compose
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

**Check if installed:**
```bash
make check-tools
```

### Step 2: Install Dependencies

```bash
make install
```

This installs all Python packages including:
- FastAPI & Uvicorn
- LangChain & LangGraph
- OpenAI SDK
- PostgreSQL & Redis drivers
- Jupyter for testing

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set your OpenAI API key
nano .env  # or use your preferred editor
```

**Required change:**
```env
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

**Optional:** Adjust model configurations (see `ENV_CONFIGURATION_GUIDE.md`)

### Step 4: Start Services

```bash
# Start PostgreSQL + Redis
make services-start

# Verify services are healthy
make status
```

### Step 5: Setup Database

```bash
# Run migrations
make db-migrate

# Load mock data
make db-seed
```

**Or do both at once:**
```bash
make db-refresh
```

### Step 6: Run the API

```bash
make api-run
```

You should see:
```
Starting FastAPI server...
API will be available at: http://localhost:8000
Docs available at: http://localhost:8000/docs
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Keep this terminal open!**

### Step 7: Test the API

**Option A: Interactive Docs (Easiest)**

1. Open http://localhost:8000/docs
2. Try the `/api/query` endpoint
3. Click "Try it out"
4. Use this example:
   ```json
   {
     "query": "What is the customer's risk score?",
     "context": {
       "cif_no": "C000001"
     },
     "user_id": "analyst_1",
     "session_id": "test_session_1"
   }
   ```
5. Click "Execute"

**Option B: Jupyter Notebook (Best for Testing)**

In a **new terminal**:
```bash
make notebook
```

Opens at http://localhost:8888

Then:
1. Navigate to `notebooks/api_testing.ipynb`
2. Run all cells: `Kernel > Restart & Run All`
3. Explore the results!

**Option C: cURL**

```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the customer'"'"'s risk score?",
    "context": {"cif_no": "C000001"},
    "user_id": "analyst_1",
    "session_id": "test_session_1"
  }'
```

---

## 🎯 What You Can Do Now

### 1. Query Customer Information

```json
{
  "query": "Get basic customer information",
  "context": {"cif_no": "C000001"},
  "user_id": "analyst_1",
  "session_id": "session_1"
}
```

### 2. Analyze AML Risk

```json
{
  "query": "Analyze this customer for AML risk and provide recommendations",
  "context": {"cif_no": "C000002"},
  "user_id": "analyst_1",
  "session_id": "session_1"
}
```

### 3. Check Transaction Patterns

```json
{
  "query": "Show me transaction patterns for the last 30 days",
  "context": {"cif_no": "C000003"},
  "user_id": "analyst_1",
  "session_id": "session_1"
}
```

### 4. Ask Compliance Questions

```json
{
  "query": "What is structuring and how can I detect it?",
  "context": {"cif_no": "C000001"},
  "user_id": "analyst_1",
  "session_id": "session_1"
}
```

### 5. Continue Conversations

Use the same `session_id` for follow-up questions:

**First query:**
```json
{
  "query": "Get customer basic info",
  "context": {"cif_no": "C000001"},
  "user_id": "analyst_1",
  "session_id": "investigation_001"
}
```

**Follow-up query:**
```json
{
  "query": "What is their risk score?",
  "context": {"cif_no": "C000001"},
  "user_id": "analyst_1",
  "session_id": "investigation_001"
}
```

---

## 🛠️ Development Workflow

### Daily Workflow

```bash
# Morning: Start everything
make status        # Check what's running
make api-run       # Start API

# During development:
make services-logs # Monitor logs (separate terminal)
make notebook      # Test changes interactively

# End of day: Stop everything
make stop
```

### Making Changes

```bash
# 1. Edit code
nano agents/coordinator.py

# 2. API auto-reloads (if using make api-run)
# No restart needed!

# 3. Test changes
# Use notebook or API docs

# 4. Format and check
make format
make lint
```

### Database Changes

```bash
# Reset database
make db-reset

# Run migrations
make db-migrate

# Reload seed data
make db-seed

# Or do all at once
make db-refresh
```

---

## 🐛 Troubleshooting

### API won't start

**Problem:** Port 8000 already in use

**Solution:**
```bash
# Find what's using the port
lsof -i :8000

# Kill it
kill -9 <PID>

# Or change port in Makefile
```

### "OpenAI API key not found"

**Problem:** API key not set or invalid

**Solution:**
```bash
# Check your .env file
cat .env | grep OPENAI_API_KEY

# Should show:
# OPENAI_API_KEY=sk-proj-...

# Verify it loads
make check-env
```

### Database connection errors

**Problem:** PostgreSQL not running

**Solution:**
```bash
make db-start
make db-status
```

### Redis connection errors

**Problem:** Redis not running

**Solution:**
```bash
make redis-start
make redis-status
```

### Empty query responses

**Problem:** Database not seeded

**Solution:**
```bash
make db-seed
```

### Services won't start

**Problem:** Docker issues

**Solution:**
```bash
# Stop everything
make services-stop

# Clean volumes
make services-clean

# Fresh start
make services-start
make db-migrate
make db-seed
```

---

## 📊 Available Mock Customers

The seeded database includes:

- **C000001-C000010**: Various risk profiles (LOW, MEDIUM, HIGH)
- Sample transactions, alerts, and risk indicators
- Different customer types and patterns

**Try these in your queries!**

---

## 🎓 Next Steps

### Learn the System

1. **Architecture** → Read `ARCHITECTURE.md`
   - Understand the multi-agent design
   - Learn about the PEAR pattern (Plan-Execute-Analyze-Review-Replan)

2. **Configuration** → Read `ENV_CONFIGURATION_GUIDE.md`
   - Model selection strategy
   - Performance tuning
   - Cost optimization

3. **Testing** → Explore `notebooks/api_testing.ipynb`
   - All API endpoints
   - Session management
   - Performance benchmarks

### Build Your Integration

1. **Frontend Integration**
   - Use the API endpoints
   - Handle session IDs
   - Display compliance analysis

2. **Custom Workflows**
   - Create specialized notebooks
   - Add custom queries
   - Build dashboards

3. **Production Deployment**
   - Configure for production
   - Set up monitoring
   - Implement authentication

---

## 📚 Documentation Index

| Document | Purpose |
|----------|---------|
| `README.md` | Project overview |
| `QUICK_START.md` | **This guide** - Getting started |
| `ARCHITECTURE.md` | System design and architecture |
| `ENV_CONFIGURATION_GUIDE.md` | Environment and agent configuration |
| `MAKEFILE_GUIDE.md` | All make commands with examples |
| `notebooks/README.md` | Notebook testing guide |
| `.make-cheatsheet` | Quick command reference |

---

## 🚀 Quick Command Reference

```bash
# Setup
make setup              # Full setup from scratch

# Daily use
make start              # Start services + API
make stop               # Stop everything
make status             # Check status

# Testing
make notebook           # Interactive API testing
make api-run            # Run API server

# Database
make db-refresh         # Fresh database
make db-shell           # Database CLI

# Development
make format             # Format code
make test               # Run tests
make clean              # Clean cache
```

---

## 💡 Pro Tips

1. **Use two terminals**: One for API, one for notebook/testing
2. **Keep logs visible**: Run `make services-logs` in a third terminal
3. **Save session IDs**: Track interesting investigations
4. **Clear cache when needed**: `make redis-flush` for fresh data
5. **Backup before refresh**: `make db-backup` before `make db-refresh`

---

## ✅ Success Checklist

- [ ] Dependencies installed (`make install`)
- [ ] OpenAI API key set in `.env`
- [ ] Services running (`make services-start`)
- [ ] Database migrated and seeded (`make db-refresh`)
- [ ] API running (`make api-run`)
- [ ] Health check passes (http://localhost:8000/health)
- [ ] First query successful (via docs or notebook)
- [ ] Notebook opened and tested (`make notebook`)

---

**🎉 You're all set! Start querying the AML Copilot!**

For help: `make help` or check the documentation files above.
