# Environment Configuration Guide

## Quick Start

1. **Copy the template:**
   ```bash
   cp .env.example .env
   ```

2. **Set your OpenAI API key:**
   ```bash
   # Edit .env and replace:
   OPENAI_API_KEY=sk-placeholder-key-replace-with-real-key
   # With your actual key from: https://platform.openai.com/api-keys
   ```

3. **Start services:**
   ```bash
   docker-compose up -d  # Starts PostgreSQL + Redis
   ```

4. **Run migrations:**
   ```bash
   poetry run alembic upgrade head
   ```

5. **Load mock data:**
   ```bash
   PYTHONPATH=/Users/souley/Desktop/code/aml_copilot poetry run python data/mock_data.py
   ```

## Configuration Sections

### 🗄️ Database Configuration

```env
DATABASE_HOST=localhost      # PostgreSQL host
DATABASE_PORT=5432          # PostgreSQL port
DATABASE_NAME=aml_compliance # Database name
DATABASE_USER=postgres      # Database user
DATABASE_PASSWORD=postgres  # Database password
```

**When to change:**
- Production: Use managed database credentials
- Different ports: If PostgreSQL runs on non-standard port

### 🔴 Redis Configuration

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB_CACHE=0         # For feature group caching
REDIS_DB_CHECKPOINTS=1   # For conversation history
```

**Key Concept:** Two separate Redis databases:
- **DB 0 (Cache)**: Feature groups, customer data
- **DB 1 (Checkpoints)**: Conversation state, session history

**When to change:**
- Production: Use managed Redis instance
- Authentication: Uncomment REDIS_PASSWORD if required

### 🤖 Agent Configurations

#### **Model Selection Strategy:**

| Agent | Current Model | Why? | When to Change |
|-------|--------------|------|----------------|
| **Coordinator** | gpt-4o-mini | Simple routing decisions, speed > power | Only if costs too high |
| **Intent Mapper** | gpt-4o-mini | Straightforward query understanding | Only if mapping accuracy poor |
| **Data Retrieval** | N/A | **Does NOT use LLM** (mechanical tool execution) | Never - no LLM needed |
| **Compliance Expert** | gpt-4o | Needs deep reasoning for AML analysis | gpt-4o-mini if budget-constrained |
| **Review Expert** | gpt-4o | Needs good judgment for QA & replanning | gpt-4o-mini if budget-constrained |

#### **Temperature Settings:**

```env
COORDINATOR_TEMPERATURE=0.0          # Deterministic routing
INTENT_MAPPER_TEMPERATURE=0.0        # Deterministic mapping
COMPLIANCE_EXPERT_TEMPERATURE=0.1    # Slight creativity for nuanced analysis
REVIEW_EXPERT_TEMPERATURE=0.1        # Slight creativity for nuanced evaluation
```

**Temperature Guide:**
- **0.0** = Deterministic, same input → same output (routing, mapping)
- **0.1-0.3** = Slight creativity (compliance analysis, writing)
- **0.7+** = High creativity (NOT recommended for compliance)

#### **Timeout Settings:**

```env
COORDINATOR_TIMEOUT=60          # Fast routing
INTENT_MAPPER_TIMEOUT=60        # Fast mapping
COMPLIANCE_EXPERT_TIMEOUT=120   # Complex analysis takes longer
REVIEW_EXPERT_TIMEOUT=120       # Thorough review takes time
```

**Note:** Data Retrieval agent doesn't have a timeout since it doesn't use an LLM.

**When to increase:**
- Slow OpenAI API responses
- Complex queries timing out
- Network latency issues

### 🔄 Review Expert Configuration

```env
REVIEW_EXPERT_MODEL=gpt-4o
REVIEW_EXPERT_TEMPERATURE=0.1
REVIEW_EXPERT_MAX_RETRIES=3
REVIEW_EXPERT_TIMEOUT=120
MAX_REVIEW_ATTEMPTS=3
```

**What it does:** The Review Expert evaluates Compliance Expert outputs and controls the Plan-Execute-Analyze-Review-Replan (PEAR) loop.

**Review Expert Decisions:**
- `needs_data` → Routes back to Intent Mapper for more data (REPLAN)
- `needs_refinement` → Routes back to Compliance Expert for better analysis (RETRY)
- `needs_clarification` → Routes back to user for more information
- `passed` → Sends response to user

`MAX_REVIEW_ATTEMPTS` prevents infinite loops by limiting how many times the Review Agent can request changes.

**Scenarios:**
- `MAX_REVIEW_ATTEMPTS=1` → No retries (fastest, least accurate, no replanning)
- `MAX_REVIEW_ATTEMPTS=3` → Balanced (default, allows 2 replans)
- `MAX_REVIEW_ATTEMPTS=5` → More quality checks (slower, allows 4 replans)

**Configuration Flow:**
```
.env (MAX_REVIEW_ATTEMPTS=3)
  ↓
Settings.max_review_attempts
  ↓
AgentsConfig.review_expert.max_review_attempts
  ↓
ReviewAgent.__init__(max_review_attempts=3)
```

**Recent Fix:** This configuration is now properly injected via `ReviewAgentConfig` instead of being accessed directly from global settings. See `REVIEW_SYSTEM_CONFIG_FIX.md` for details.

**See Also:** `ARCHITECTURE.md` - "Plan-Execute-Analyze-Review-Replan Pattern" section for detailed workflow documentation.

### 💾 Cache Configuration

```env
CACHE_TTL=3600           # 1 hour default
ENABLE_CACHING=true      # Enable/disable all caching
```

**Cache TTLs by Feature Group** (in code, not .env):
- Basic info: 1 hour (rarely changes)
- Transaction features: 5 minutes (updates frequently)
- Network features: 30 minutes (expensive graph analysis)
- Knowledge graph: 2 hours (external data, slow to change)

**When to disable caching:**
- Development/testing (want fresh data)
- Debugging cache issues
- Data migration in progress

### 📝 Logging

```env
LOG_LEVEL=INFO
```

**Options:**
- `DEBUG` - Very verbose (development)
- `INFO` - Standard logging (default)
- `WARNING` - Only warnings/errors
- `ERROR` - Only errors
- `CRITICAL` - Only critical failures

## Environment-Specific Configurations

### Development

```env
# Use cheap models
COMPLIANCE_EXPERT_MODEL=gpt-4o-mini  # Save costs

# Shorter timeouts
COMPLIANCE_EXPERT_TIMEOUT=60

# More logging
LOG_LEVEL=DEBUG

# Disable caching for testing
ENABLE_CACHING=false
```

### Staging

```env
# Production-like models
COMPLIANCE_EXPERT_MODEL=gpt-4o

# Standard timeouts
COMPLIANCE_EXPERT_TIMEOUT=120

# Moderate logging
LOG_LEVEL=INFO

# Enable caching
ENABLE_CACHING=true
```

### Production

```env
# Production database
DATABASE_HOST=prod-db.example.com
DATABASE_PASSWORD=<strong-password>

# Production Redis
REDIS_HOST=prod-redis.example.com
REDIS_PASSWORD=<redis-password>

# Production models
COMPLIANCE_EXPERT_MODEL=gpt-4o

# Longer timeouts for reliability
COORDINATOR_TIMEOUT=120
COMPLIANCE_EXPERT_TIMEOUT=180

# Production logging
LOG_LEVEL=WARNING

# Enable caching
ENABLE_CACHING=true
```

## Cost Optimization

### Budget-Conscious Setup

```env
# Use only gpt-4o-mini everywhere
COORDINATOR_MODEL=gpt-4o-mini
INTENT_MAPPER_MODEL=gpt-4o-mini
COMPLIANCE_EXPERT_MODEL=gpt-4o-mini  # ⚠️ May reduce quality
REVIEW_EXPERT_MODEL=gpt-4o-mini      # ⚠️ May reduce quality

# Aggressive caching
CACHE_TTL=7200  # 2 hours
ENABLE_CACHING=true

# Fewer retries
COORDINATOR_MAX_RETRIES=1
INTENT_MAPPER_MAX_RETRIES=1
COMPLIANCE_EXPERT_MAX_RETRIES=1
REVIEW_EXPERT_MAX_RETRIES=1

# Limit review cycles
MAX_REVIEW_ATTEMPTS=1
```

**Trade-offs:**
- ✅ ~80% cost savings
- ❌ Less accurate AML analysis
- ❌ Fewer quality checks

### Quality-First Setup

```env
# Use best models
COMPLIANCE_EXPERT_MODEL=gpt-4o
REVIEW_EXPERT_MODEL=gpt-4o

# More retries for reliability
COMPLIANCE_EXPERT_MAX_RETRIES=5
REVIEW_EXPERT_MAX_RETRIES=5

# More review cycles
MAX_REVIEW_ATTEMPTS=5

# Longer timeouts
COMPLIANCE_EXPERT_TIMEOUT=180
REVIEW_EXPERT_TIMEOUT=180
```

**Trade-offs:**
- ✅ Higher accuracy
- ✅ Better AML detection
- ❌ Higher costs
- ❌ Slower responses

## Common Issues

### "OpenAI API key not found"

**Problem:** Missing or invalid API key

**Solution:**
```env
# Make sure this is set in .env:
OPENAI_API_KEY=sk-proj-...your-actual-key...
```

### "Redis connection refused"

**Problem:** Redis not running

**Solution:**
```bash
# Start Redis via docker-compose
docker-compose up -d redis

# Or check if Redis is running:
redis-cli ping
```

### "Database does not exist"

**Problem:** PostgreSQL database not created

**Solution:**
```bash
# Start PostgreSQL
docker-compose up -d postgres

# Database is auto-created via POSTGRES_DB in docker-compose.yml
```

### "Agent timeout"

**Problem:** Queries taking too long

**Solution:**
```env
# Increase timeout for specific agent:
COMPLIANCE_EXPERT_TIMEOUT=300  # 5 minutes
```

### "Rate limit exceeded"

**Problem:** Too many OpenAI API requests

**Solution:**
1. Enable caching: `ENABLE_CACHING=true`
2. Use cheaper models for non-critical agents
3. Reduce max retries
4. Add rate limiting in code (future enhancement)

## Testing Your Configuration

**1. Verify settings loaded:**
```python
from config.settings import settings

print(f"Database: {settings.database_url}")
print(f"Redis Cache DB: {settings.redis_db_cache}")
print(f"Compliance Model: {settings.compliance_expert_model}")
```

**2. Test database connection:**
```bash
poetry run python -c "
from db.manager import db_manager
with db_manager.get_connection() as conn:
    print('✓ Database connected')
"
```

**3. Test Redis connection:**
```bash
poetry run python -c "
from db.services.cache_service import cache_service
if cache_service.health_check():
    print('✓ Redis connected')
"
```

**4. Test OpenAI API:**
```bash
poetry run python -c "
from langchain_openai import ChatOpenAI
from config.settings import settings
llm = ChatOpenAI(model=settings.coordinator_model)
response = llm.invoke('test')
print('✓ OpenAI API working')
"
```

## Best Practices

1. **Never commit .env to git** - Keep secrets safe
2. **Use .env.example as template** - Document all required vars
3. **Different .env per environment** - .env.dev, .env.staging, .env.prod
4. **Rotate API keys regularly** - Security best practice
5. **Monitor costs** - Track OpenAI usage in dashboard
6. **Test changes locally** - Before deploying to production

## Security Checklist

- [ ] Strong database password (production)
- [ ] Redis password set (production)
- [ ] OpenAI API key kept secret
- [ ] .env not in version control
- [ ] Environment-specific configs separated
- [ ] API keys rotated regularly
- [ ] Logs don't contain secrets

## Related Documentation

- `ARCHITECTURE.md` - System design
- `SESSION_CONTINUATION.md` - Session management
- `docker-compose.yml` - Container configuration
- `config/settings.py` - Settings schema
