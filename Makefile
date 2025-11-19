.PHONY: help install services-start services-stop services-status services-logs
.PHONY: db-start db-stop db-status db-migrate db-reset db-seed db-refresh db-shell
.PHONY: redis-start redis-stop redis-status redis-cli redis-flush
.PHONY: api-run api-dev test clean format lint

.DEFAULT_GOAL := help

# Variables
PYTHON := PYTHONPATH=$(CURDIR) poetry run python
ALEMBIC := poetry run alembic
DOCKER_COMPOSE := docker-compose
PROJECT_NAME := aml-copilot

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ Help

help: ## Show this help message
	@echo "$(GREEN)AML Copilot - Available Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make $(YELLOW)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Installation

install: ## Install project dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	poetry install
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

##@ Docker Services

services-start: ## Start all services (PostgreSQL + Redis)
	@echo "$(GREEN)Starting all services...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@$(MAKE) services-status

services-stop: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✓ Services stopped$(NC)"

services-restart: ## Restart all services
	@$(MAKE) services-stop
	@$(MAKE) services-start

services-status: ## Check status of all services
	@echo "$(GREEN)Service Status:$(NC)"
	@$(DOCKER_COMPOSE) ps

services-logs: ## Show logs from all services
	$(DOCKER_COMPOSE) logs -f

services-clean: ## Stop services and remove volumes (DESTRUCTIVE!)
	@echo "$(RED)⚠️  This will DELETE all data in PostgreSQL and Redis!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(DOCKER_COMPOSE) down -v; \
		echo "$(GREEN)✓ Services stopped and volumes removed$(NC)"; \
	else \
		echo "$(YELLOW)Aborted$(NC)"; \
	fi

##@ Database Management

db-start: ## Start only PostgreSQL
	@echo "$(GREEN)Starting PostgreSQL...$(NC)"
	$(DOCKER_COMPOSE) up -d postgres
	@sleep 3
	@$(MAKE) db-status

db-stop: ## Stop only PostgreSQL
	@echo "$(YELLOW)Stopping PostgreSQL...$(NC)"
	$(DOCKER_COMPOSE) stop postgres
	@echo "$(GREEN)✓ PostgreSQL stopped$(NC)"

db-status: ## Check PostgreSQL connection
	@echo "$(GREEN)Checking PostgreSQL connection...$(NC)"
	@$(DOCKER_COMPOSE) exec postgres pg_isready -U postgres && \
		echo "$(GREEN)✓ PostgreSQL is ready$(NC)" || \
		echo "$(RED)✗ PostgreSQL is not ready$(NC)"

db-migrate: ## Run database migrations
	@echo "$(GREEN)Running migrations...$(NC)"
	$(ALEMBIC) upgrade head
	@echo "$(GREEN)✓ Migrations completed$(NC)"

db-downgrade: ## Rollback last migration
	@echo "$(YELLOW)Rolling back last migration...$(NC)"
	$(ALEMBIC) downgrade -1
	@echo "$(GREEN)✓ Migration rolled back$(NC)"

db-reset: ## Drop and recreate database (DESTRUCTIVE!)
	@echo "$(RED)⚠️  This will DELETE all data in the database!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(DOCKER_COMPOSE) exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS aml_compliance;"; \
		$(DOCKER_COMPOSE) exec postgres psql -U postgres -c "CREATE DATABASE aml_compliance;"; \
		echo "$(GREEN)✓ Database reset$(NC)"; \
	else \
		echo "$(YELLOW)Aborted$(NC)"; \
	fi

db-seed: ## Load mock data into database
	@echo "$(GREEN)Loading mock data...$(NC)"
	$(PYTHON) data/mock_data.py
	@echo "$(GREEN)✓ Mock data loaded$(NC)"

db-refresh: ## Full database refresh (reset + migrate + seed)
	@echo "$(GREEN)Refreshing database...$(NC)"
	@$(MAKE) db-reset SKIP_CONFIRM=1
	@$(MAKE) db-migrate
	@$(MAKE) db-seed
	@echo "$(GREEN)✓ Database refreshed successfully$(NC)"

db-shell: ## Open PostgreSQL shell
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d aml_compliance

db-backup: ## Backup database to file
	@echo "$(GREEN)Backing up database...$(NC)"
	@mkdir -p backups
	$(DOCKER_COMPOSE) exec -T postgres pg_dump -U postgres aml_compliance > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✓ Database backed up to backups/$(NC)"

db-restore: ## Restore database from latest backup
	@echo "$(YELLOW)Restoring from latest backup...$(NC)"
	@latest=$$(ls -t backups/*.sql 2>/dev/null | head -1); \
	if [ -z "$$latest" ]; then \
		echo "$(RED)✗ No backup files found$(NC)"; \
		exit 1; \
	fi; \
	echo "Restoring from $$latest"; \
	cat "$$latest" | $(DOCKER_COMPOSE) exec -T postgres psql -U postgres aml_compliance
	@echo "$(GREEN)✓ Database restored$(NC)"

##@ Redis Management

redis-start: ## Start only Redis
	@echo "$(GREEN)Starting Redis...$(NC)"
	$(DOCKER_COMPOSE) up -d redis
	@sleep 2
	@$(MAKE) redis-status

redis-stop: ## Stop only Redis
	@echo "$(YELLOW)Stopping Redis...$(NC)"
	$(DOCKER_COMPOSE) stop redis
	@echo "$(GREEN)✓ Redis stopped$(NC)"

redis-status: ## Check Redis connection
	@echo "$(GREEN)Checking Redis connection...$(NC)"
	@$(DOCKER_COMPOSE) exec redis redis-cli ping && \
		echo "$(GREEN)✓ Redis is ready$(NC)" || \
		echo "$(RED)✗ Redis is not ready$(NC)"

redis-cli: ## Open Redis CLI
	$(DOCKER_COMPOSE) exec redis redis-cli

redis-flush: ## Flush all Redis data (DESTRUCTIVE!)
	@echo "$(RED)⚠️  This will DELETE all cached data in Redis!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(DOCKER_COMPOSE) exec redis redis-cli FLUSHALL; \
		echo "$(GREEN)✓ Redis flushed$(NC)"; \
	else \
		echo "$(YELLOW)Aborted$(NC)"; \
	fi

redis-info: ## Show Redis info and stats
	@echo "$(GREEN)Redis Information:$(NC)"
	@$(DOCKER_COMPOSE) exec redis redis-cli INFO | grep -E "redis_version|used_memory_human|connected_clients|total_commands_processed"

##@ API Management

api-run: ## Run the FastAPI application
	@echo "$(GREEN)Starting FastAPI server...$(NC)"
	@echo "API will be available at: http://localhost:8000"
	@echo "Docs available at: http://localhost:8000/docs"
	$(PYTHON) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

api-dev: services-start ## Start services and run API in development mode
	@echo "$(GREEN)Starting development environment...$(NC)"
	@sleep 3
	@$(MAKE) api-run

api-prod: ## Run API in production mode (no reload)
	@echo "$(GREEN)Starting FastAPI server in production mode...$(NC)"
	$(PYTHON) -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

##@ Testing & Quality

test: ## Run tests
	@echo "$(GREEN)Running tests...$(NC)"
	$(PYTHON) -m pytest tests/ -v

test-coverage: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(PYTHON) -m pytest tests/ --cov=. --cov-report=html --cov-report=term

lint: ## Run linting checks
	@echo "$(GREEN)Running linting...$(NC)"
	poetry run ruff check .

format: ## Format code with black and ruff
	@echo "$(GREEN)Formatting code...$(NC)"
	poetry run black .
	poetry run ruff check --fix .

##@ Development Helpers

clean: ## Clean up cache and temporary files
	@echo "$(GREEN)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

logs-api: ## Show API logs (if running in background)
	tail -f logs/api.log

shell: ## Open Python shell with project context
	@echo "$(GREEN)Opening Python shell with project context...$(NC)"
	$(PYTHON)

check-env: ## Verify environment configuration
	@echo "$(GREEN)Checking environment configuration...$(NC)"
	@$(PYTHON) -c "from config.settings import settings; print('✓ Settings loaded'); print(f'Database: {settings.database_url}'); print(f'Redis: {settings.redis_url}'); print(f'OpenAI: {\"Configured\" if settings.openai_api_key and not settings.openai_api_key.startswith(\"sk-placeholder\") else \"Missing/Placeholder\"}')"

check-tools: ## Verify all required tools are installed
	@echo "$(GREEN)Checking required tools...$(NC)"
	@command -v docker >/dev/null 2>&1 && echo "✓ Docker installed" || echo "✗ Docker not found"
	@command -v docker-compose >/dev/null 2>&1 && echo "✓ Docker Compose installed" || echo "✗ Docker Compose not found"
	@command -v poetry >/dev/null 2>&1 && echo "✓ Poetry installed" || echo "✗ Poetry not found"
	@command -v python3 >/dev/null 2>&1 && echo "✓ Python3 installed" || echo "✗ Python3 not found"

##@ Quick Start Commands

setup: install services-start db-migrate db-seed ## Complete setup (install + start services + setup DB)
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "$(GREEN)========================================$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Set your OpenAI API key in .env"
	@echo "  2. Run: $(YELLOW)make api-run$(NC)"
	@echo "  3. Visit: $(YELLOW)http://localhost:8000/docs$(NC)"
	@echo ""

start: services-start api-run ## Start services and API (quick start)

stop: services-stop ## Stop all services

restart: services-restart api-run ## Restart services and API

status: ## Show status of all components
	@echo "$(GREEN)=== System Status ===$(NC)"
	@echo ""
	@echo "$(YELLOW)Docker Services:$(NC)"
	@$(MAKE) services-status
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@$(MAKE) db-status
	@echo ""
	@echo "$(YELLOW)Redis:$(NC)"
	@$(MAKE) redis-status
	@echo ""
	@echo "$(YELLOW)Environment:$(NC)"
	@$(MAKE) check-env
