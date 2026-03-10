.PHONY: dev stop test lint format migrate seed clean setup setup-hooks help

COMPOSE = docker compose -f infra/compose.dev.yaml

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: setup-hooks ## First-time setup: copy env files, install git hooks
	@test -f infra/env.dev || cp infra/env.dev.example infra/env.dev
	@echo "✓ Environment files ready. Edit infra/env.dev as needed."

setup-hooks: ## Install git hooks (blocks direct pushes to main)
	@ln -sf ../../infra/git-hooks/pre-push .git/hooks/pre-push
	@chmod +x infra/git-hooks/pre-push
	@echo "✓ Git hooks installed. Direct pushes to main are now blocked."

dev: setup ## Start all services (docker compose up --build)
	$(COMPOSE) up --build

dev-d: setup ## Start all services in background
	$(COMPOSE) up --build -d

stop: ## Stop all services
	$(COMPOSE) down

test: ## Run all tests
	$(COMPOSE) run --rm api pytest -v

test-local: ## Run backend tests locally (no Docker)
	cd api && python -m pytest -v

lint: ## Run linters (ruff + eslint)
	$(COMPOSE) run --rm api ruff check .
	$(COMPOSE) run --rm web npm run lint

lint-local: ## Run linters locally (no Docker)
	cd api && ruff check .
	cd web && npm run lint

format: ## Auto-format code (ruff + prettier)
	$(COMPOSE) run --rm api ruff format .
	$(COMPOSE) run --rm api ruff check --fix .
	$(COMPOSE) run --rm web npm run format

format-local: ## Auto-format locally (no Docker)
	cd api && ruff format . && ruff check --fix .
	cd web && npm run format

migrate: ## Run database migrations
	$(COMPOSE) run --rm api alembic upgrade head

migrate-local: ## Run migrations locally (no Docker)
	cd api && alembic upgrade head

migration: ## Create a new migration (usage: make migration MSG="description")
	$(COMPOSE) run --rm api alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed test data (requires seed module — see Sprint 1)
	@echo "⚠ Seed module not yet implemented. See docs/TASKS.md Sprint 1."

clean: ## Stop services and remove volumes
	$(COMPOSE) down -v
	@echo "✓ All containers and volumes removed."

logs: ## Tail logs for all services
	$(COMPOSE) logs -f

logs-api: ## Tail API logs only
	$(COMPOSE) logs -f api

logs-web: ## Tail frontend logs only
	$(COMPOSE) logs -f web

shell-api: ## Open a shell in the API container
	$(COMPOSE) exec api bash

shell-web: ## Open a shell in the web container
	$(COMPOSE) exec web sh

db: ## Open psql in the database container
	$(COMPOSE) exec postgres psql -U filefree -d filefree_dev
