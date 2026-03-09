.PHONY: dev stop test lint format migrate seed clean setup help

COMPOSE = docker compose -f infra/compose.dev.yaml

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup: copy env files
	@test -f infra/env.dev || cp infra/env.dev.example infra/env.dev
	@echo "✓ Environment files ready. Edit infra/env.dev as needed."

dev: setup ## Start all services (docker compose up --build)
	$(COMPOSE) up --build

dev-d: setup ## Start all services in background
	$(COMPOSE) up --build -d

stop: ## Stop all services
	$(COMPOSE) down

test: ## Run all tests
	$(COMPOSE) exec api pytest -v

test-local: ## Run backend tests locally (no Docker)
	cd api && python -m pytest -v

lint: ## Run linters (ruff + eslint)
	$(COMPOSE) exec api ruff check .
	$(COMPOSE) exec web npm run lint

lint-local: ## Run linters locally (no Docker)
	cd api && ruff check .
	cd web && npm run lint

format: ## Auto-format code (ruff + prettier)
	$(COMPOSE) exec api ruff format .
	$(COMPOSE) exec api ruff check --fix .
	$(COMPOSE) exec web npm run format

format-local: ## Auto-format locally (no Docker)
	cd api && ruff format . && ruff check --fix .
	cd web && npm run format

migrate: ## Run database migrations (alembic upgrade head)
	$(COMPOSE) exec api alembic upgrade head

seed: ## Seed test data
	$(COMPOSE) exec api python -m app.seed

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
