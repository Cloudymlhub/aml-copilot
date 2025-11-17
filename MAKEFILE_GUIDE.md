# Makefile Quick Reference Guide

## 🚀 Quick Start

### First Time Setup
```bash
# Complete setup from scratch
make setup

# This runs:
# - make install (install dependencies)
# - make services-start (start PostgreSQL + Redis)
# - make db-migrate (run migrations)
# - make db-seed (load mock data)
```

### Daily Development Workflow
```bash
# Start everything and run API
make start

# Or start services only
make services-start

# Then run API separately
make api-run
```

### Stop Everything
```bash
make stop
```

---

## 📋 Common Tasks

### Running the API

```bash
# Development mode (with auto-reload)
make api-run

# Development mode with automatic service startup
make api-dev

# Production mode (4 workers, no reload)
make api-prod
```

**API URLs:**
- Main API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Database Operations

```bash
# Start database
make db-start

# Run migrations
make db-migrate

# Load mock data
make db-seed

# Refresh database (drop, recreate, migrate, seed) - DESTRUCTIVE!
make db-refresh

# Backup database
make db-backup

# Restore from latest backup
make db-restore

# Open database shell
make db-shell
```

### Redis Operations

```bash
# Start Redis
make redis-start

# Check Redis status
make redis-status

# Open Redis CLI
make redis-cli

# Show Redis stats
make redis-info

# Clear all Redis cache - DESTRUCTIVE!
make redis-flush
```

---

## 🔧 Service Management

### Start/Stop Services

```bash
# Start all services (PostgreSQL + Redis)
make services-start

# Stop all services
make services-stop

# Restart all services
make services-restart

# Check service status
make services-status

# View service logs (live)
make services-logs
```

### Clean Everything (DESTRUCTIVE!)

```bash
# Remove all Docker volumes (deletes all data)
make services-clean
```

---

## 🧪 Development Tools

### Testing

```bash
# Run tests
make test

# Run tests with coverage report
make test-coverage
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Clean cache files
make clean
```

### Debugging Helpers

```bash
# Check system status
make status

# Verify environment configuration
make check-env

# Check installed tools
make check-tools

# Open Python shell with project context
make shell
```

---

## 📊 Common Workflows

### Workflow 1: Starting Development for the Day

```bash
# Check what's running
make status

# Start services if needed
make services-start

# Run the API
make api-run
```

### Workflow 2: Fresh Database Refresh

```bash
# WARNING: This deletes all data!
make db-refresh

# Or step by step:
make db-reset      # Drop and recreate database
make db-migrate    # Run migrations
make db-seed       # Load mock data
```

### Workflow 3: Debugging Database Issues

```bash
# Check if database is running
make db-status

# Open database shell to inspect
make db-shell

# Query example:
# SELECT * FROM customers LIMIT 5;
```

### Workflow 4: Debugging Redis Cache Issues

```bash
# Check Redis status
make redis-status

# View Redis info
make redis-info

# Open Redis CLI
make redis-cli

# In Redis CLI:
# KEYS *              # List all keys
# GET key_name        # Get value
# FLUSHALL           # Clear everything (or use make redis-flush)
```

### Workflow 5: Complete System Reset

```bash
# Stop everything
make services-stop

# Clean volumes (deletes data)
make services-clean

# Fresh setup
make setup

# Run API
make api-run
```

### Workflow 6: Deploying Changes

```bash
# Format code
make format

# Run linting
make lint

# Run tests
make test

# If all pass, commit changes
git add .
git commit -m "Your message"
```

---

## 🚨 Troubleshooting

### "Port already in use"

**Problem:** Another service is using port 5432 (PostgreSQL) or 6379 (Redis)

**Solution:**
```bash
# Check what's using the port
lsof -i :5432
lsof -i :6379

# Stop our services
make services-stop

# Kill the process using the port (if not our service)
kill -9 <PID>

# Restart our services
make services-start
```

### "Database does not exist"

**Problem:** Database not created or migrations not run

**Solution:**
```bash
make db-start
make db-migrate
```

### "OpenAI API key not found"

**Problem:** Missing or invalid API key in .env

**Solution:**
```bash
# Edit .env and set your real API key
# OPENAI_API_KEY=sk-proj-your-actual-key

# Verify configuration
make check-env
```

### "Redis connection refused"

**Problem:** Redis not running

**Solution:**
```bash
make redis-start
make redis-status
```

### "Clean everything and start fresh"

**Solution:**
```bash
make services-stop
make clean
make setup
```

---

## 📝 Advanced Tips

### Running Commands in Background

```bash
# Start services in background (already default)
make services-start

# Run API in background (use screen/tmux or nohup)
nohup make api-run > logs/api.log 2>&1 &

# View logs
make logs-api
```

### Database Migrations

```bash
# Create new migration
poetry run alembic revision -m "description"

# Apply migrations
make db-migrate

# Rollback last migration
make db-downgrade

# View migration history
poetry run alembic history
```

### Custom Database Operations

```bash
# Export data to CSV
make db-shell
# Then in psql:
# \copy (SELECT * FROM customers) TO 'customers.csv' WITH CSV HEADER;

# Import data from CSV
# \copy customers FROM 'customers.csv' WITH CSV HEADER;
```

### Redis Cache Management

```bash
# View cache keys
make redis-cli
# In Redis:
# KEYS cache:*
# KEYS checkpoint:*

# Monitor Redis commands live
make redis-cli
# Then: MONITOR

# View memory usage
make redis-info
```

---

## 🎯 Environment-Specific Commands

### Development
```bash
make api-dev           # Auto-reload enabled
LOG_LEVEL=DEBUG make api-run
```

### Staging
```bash
make api-run           # Standard settings from .env
```

### Production
```bash
make api-prod          # 4 workers, no reload, optimized
```

---

## 🔍 Quick Reference Table

| Task | Command |
|------|---------|
| **First time setup** | `make setup` |
| **Start everything** | `make start` |
| **Stop everything** | `make stop` |
| **Check status** | `make status` |
| **Run API** | `make api-run` |
| **Refresh database** | `make db-refresh` |
| **View logs** | `make services-logs` |
| **Clean cache** | `make clean` |
| **Run tests** | `make test` |
| **Format code** | `make format` |
| **Database shell** | `make db-shell` |
| **Redis CLI** | `make redis-cli` |

---

## 📚 Related Documentation

- `.env` - Environment configuration
- `ENV_CONFIGURATION_GUIDE.md` - Detailed configuration guide
- `ARCHITECTURE.md` - System architecture
- `README.md` - Project overview

---

## 💡 Pro Tips

1. **Always check status first**: `make status` before starting work
2. **Use tab completion**: Type `make <tab>` to see available commands
3. **Backup before refresh**: Run `make db-backup` before `make db-refresh`
4. **Monitor logs during development**: Keep `make services-logs` running in a separate terminal
5. **Clean regularly**: Run `make clean` to remove cache files

---

**Need help?** Run `make help` to see all available commands with descriptions.
