.PHONY: dev dev-d dev-all dev-filefree dev-launchfree dev-studio dev-trinkets dev-distill stop test lint format migrate seed clean setup setup-hooks help

COMPOSE = docker compose -p filefree -f infra/compose.dev.yaml

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: setup-hooks ## First-time setup: copy env files, install git hooks
	@test -f infra/env.dev || cp infra/env.dev.example infra/env.dev
	@echo "✓ Environment files ready. Edit infra/env.dev as needed."

setup-hooks: ## Install git hooks (blocks direct pushes to main)
	@ln -sf ../../infra/git-hooks/pre-push .git/hooks/pre-push
	@chmod +x infra/git-hooks/pre-push
	@echo "✓ Git hooks installed. Direct pushes to main are now blocked."

dev: dev-all ## Alias for full local stack

dev-all: setup ## Start all services (all apps + APIs)
	$(COMPOSE) up --build

dev-d: setup ## Start all services in background
	$(COMPOSE) up --build -d

dev-filefree: setup ## Start FileFree app + API + deps
	$(COMPOSE) up --build postgres redis api-filefree web-filefree

dev-launchfree: setup ## Start LaunchFree app + API + deps
	$(COMPOSE) up --build postgres redis api-launchfree web-launchfree

dev-studio: setup ## Start Studio app + deps
	$(COMPOSE) up --build postgres redis api-filefree web-studio

dev-trinkets: setup ## Start Trinkets app only
	$(COMPOSE) up --build web-trinkets

dev-distill: setup ## Start Distill app only
	$(COMPOSE) up --build web-distill

stop: ## Stop all services
	$(COMPOSE) down

test: ## Run all tests
	$(COMPOSE) run --rm api-filefree pytest -v

test-local: ## Run backend tests locally (no Docker)
	cd apis/filefree && python -m pytest -v

lint: ## Run linters (ruff + eslint)
	$(COMPOSE) run --rm api-filefree ruff check .
	$(COMPOSE) run --rm web-filefree npm run lint

lint-local: ## Run linters locally (no Docker)
	cd apis/filefree && ruff check .
	pnpm --filter @paperwork-labs/filefree lint

format: ## Auto-format code (ruff + prettier)
	$(COMPOSE) run --rm api-filefree ruff format .
	$(COMPOSE) run --rm api-filefree ruff check --fix .
	$(COMPOSE) run --rm web-filefree npm run format

format-local: ## Auto-format locally (no Docker)
	cd apis/filefree && ruff format . && ruff check --fix .
	pnpm --filter @paperwork-labs/filefree format

migrate: ## Run database migrations
	$(COMPOSE) run --rm api-filefree alembic upgrade head

migrate-local: ## Run migrations locally (no Docker)
	cd apis/filefree && alembic upgrade head

migration: ## Create a new migration (usage: make migration MSG="description")
	$(COMPOSE) run --rm api-filefree alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed test data (requires seed module — see Sprint 1)
	@echo "⚠ Seed module not yet implemented. See docs/TASKS.md Sprint 1."

clean: ## Stop services and remove volumes
	$(COMPOSE) down -v
	@echo "✓ All containers and volumes removed."

logs: ## Tail logs for all services
	$(COMPOSE) logs -f

logs-api: ## Tail API logs only
	$(COMPOSE) logs -f api-filefree api-launchfree

logs-web: ## Tail frontend logs only
	$(COMPOSE) logs -f web-filefree web-launchfree web-trinkets web-studio web-distill

shell-api: ## Open a shell in the API container
	$(COMPOSE) exec api-filefree bash

shell-web: ## Open a shell in the web container
	$(COMPOSE) exec web-filefree sh

db: ## Open psql in the database container
	$(COMPOSE) exec postgres psql -U filefree -d filefree_dev
