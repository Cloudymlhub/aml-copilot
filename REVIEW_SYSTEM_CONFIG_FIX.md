# Review System Configuration Fix

## Issue
The review system's `MAX_REVIEW_ATTEMPTS` configuration was:
1. Missing from `AgentsConfig` class
2. Not being passed through the configuration injection system
3. Being accessed directly from global `settings` in agents (anti-pattern)
4. Had a typo in `agent_config.py` (class name was `a` instead of `AgentsConfig`)

## Changes Made

### 1. Fixed `config/agent_config.py`
- **Fixed typo**: `class a(BaseModel):` → `class AgentsConfig(BaseModel):`
- **Added field**: `max_review_attempts: int` to `AgentsConfig` class
- **Updated example**: Added `max_review_attempts: 3` to the example JSON

### 2. Updated `config/settings.py`
- **Added to `get_agents_config()`**: Now passes `max_review_attempts=self.max_review_attempts` when creating `AgentsConfig`

### 3. Updated `agents/review_agent.py`
- **Modified `ReviewAgent.__init__()`**: Now accepts `max_review_attempts` as a parameter instead of accessing `settings.max_review_attempts`
- **Modified `create_review_agent_node()`**: Now accepts and passes `max_review_attempts` parameter
- **Removed import**: Removed `from config.settings import settings` (no longer needed)

### 4. Updated `agents/graph.py`
- **Updated review agent creation**: Now passes `max_review_attempts=agents_config.max_review_attempts`
- **Refactored `route_after_review()`**: Moved from module-level function to closure inside `create_aml_copilot_graph()` so it can access `agents_config.max_review_attempts`
- **Removed direct settings access**: No longer uses `settings.max_review_attempts` directly

## Benefits

### ✅ Proper Dependency Injection
- Configuration flows from `.env` → `Settings` → `AgentsConfig` → individual agents
- No direct access to global `settings` in agent code

### ✅ Testability
- Agents can be tested with different configurations without changing global settings
- Easy to mock configurations in tests

### ✅ Maintainability
- Clear configuration ownership
- Single source of truth for agent configurations
- Type-safe configuration with Pydantic validation

### ✅ Consistency
- Review system configuration follows the same pattern as other agent configurations
- All agent-related configs are in `AgentsConfig`

## Configuration Flow

```
.env file
  ↓
Settings.max_review_attempts (int = 3)
  ↓
Settings.get_agents_config()
  ↓
AgentsConfig.max_review_attempts (int)
  ↓
create_review_agent_node(config, max_review_attempts)
  ↓
ReviewAgent.__init__(config, max_review_attempts)
  ↓
self.max_review_attempts = max_review_attempts
```

## Testing

```bash
# Verify configuration loads correctly
PYTHONPATH=/Users/souley/Desktop/code/aml_copilot poetry run python -c "
from config.settings import settings
agents_config = settings.get_agents_config()
print(f'max_review_attempts: {agents_config.max_review_attempts}')
"
```

## Environment Variables

The following environment variable is now properly integrated:

```env
# Review System Configuration
MAX_REVIEW_ATTEMPTS=3  # Maximum review cycles before forcing completion
```

This can be adjusted per environment:
- **Development**: `MAX_REVIEW_ATTEMPTS=1` (fast iteration)
- **Staging**: `MAX_REVIEW_ATTEMPTS=3` (balanced)
- **Production**: `MAX_REVIEW_ATTEMPTS=5` (higher quality)

## Related Files

- `config/agent_config.py` - Configuration models
- `config/settings.py` - Settings loader and AgentsConfig factory
- `agents/review_agent.py` - Review agent implementation
- `agents/graph.py` - Graph construction with routing logic
- `.env` - Environment configuration
- `ENV_CONFIGURATION_GUIDE.md` - Configuration documentation
