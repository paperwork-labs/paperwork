.PHONY: dev dev-d dev-all dev-filefree dev-launchfree dev-studio dev-trinkets dev-distill \
	dev-local-filefree dev-local-launchfree dev-local-studio dev-local-trinkets dev-local-distill \
	stop test test-local lint lint-local format format-local migrate migrate-local migration seed clean \
	setup setup-hooks bootstrap help logs logs-api logs-web shell-api shell-web db env-pull env-check \
	n8n-activate-inactive

COMPOSE_PROJECT ?= paperwork
COMPOSE = docker compose -p $(COMPOSE_PROJECT) -f infra/compose.dev.yaml
API ?= filefree
API_SERVICE ?= api-$(API)
WEB_SERVICE ?= web-filefree

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: setup-hooks ## First-time setup: copy env files, install git hooks
	@test -f infra/env.dev || cp infra/env.dev.example infra/env.dev
	@echo "✓ Environment files ready. Edit infra/env.dev as needed."

setup-hooks: ## Install git hooks (blocks direct pushes to main)
	@ln -sf ../../infra/git-hooks/pre-push .git/hooks/pre-push
	@chmod +x infra/git-hooks/pre-push
	@echo "✓ Git hooks installed. Direct pushes to main are now blocked."

bootstrap: ## Bootstrap dev machine: SECRETS_API_KEY → .env.local, vault → .env.secrets (interactive or set env)
	@chmod +x scripts/bootstrap-dev.sh
	@./scripts/bootstrap-dev.sh

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
	$(COMPOSE) up --build postgres redis web-studio

dev-trinkets: setup ## Start Trinkets app only
	$(COMPOSE) up --build web-trinkets

dev-distill: setup ## Start Distill app only
	$(COMPOSE) up --build web-distill

dev-local-filefree: ## Run FileFree app locally (no Docker)
	pnpm dev:filefree

dev-local-launchfree: ## Run LaunchFree app locally (no Docker)
	pnpm dev:launchfree

dev-local-studio: ## Run Studio app locally (no Docker)
	pnpm dev:studio

dev-local-trinkets: ## Run Trinkets app locally (no Docker)
	pnpm dev:trinkets

dev-local-distill: ## Run Distill app locally (no Docker)
	pnpm dev:distill

stop: ## Stop all services
	$(COMPOSE) down

test: ## Run all tests
	$(COMPOSE) run --rm api-filefree pytest -v
	$(COMPOSE) run --rm api-launchfree sh -lc 'if [ -d tests ]; then pytest -v; else echo "No tests found for launchfree"; fi'

test-local: ## Run backend tests locally (no Docker)
	cd apis/filefree && python -m pytest -v
	cd apis/launchfree && if [ -d tests ]; then python -m pytest -v; else echo "No tests found for launchfree"; fi

lint: ## Run linters across APIs + apps
	$(COMPOSE) run --rm api-filefree ruff check .
	$(COMPOSE) run --rm api-launchfree ruff check .
	$(COMPOSE) run --rm web-filefree pnpm run lint
	$(COMPOSE) run --rm web-launchfree pnpm run lint
	$(COMPOSE) run --rm web-studio pnpm run lint
	$(COMPOSE) run --rm web-trinkets pnpm run lint
	$(COMPOSE) run --rm web-distill pnpm run lint

lint-local: ## Run linters locally across workspace
	cd apis/filefree && ruff check .
	cd apis/launchfree && ruff check .
	pnpm -r --if-present lint

format: ## Auto-format code across APIs + apps
	$(COMPOSE) run --rm api-filefree ruff format .
	$(COMPOSE) run --rm api-filefree ruff check --fix .
	$(COMPOSE) run --rm api-launchfree ruff format .
	$(COMPOSE) run --rm api-launchfree ruff check --fix .
	$(COMPOSE) run --rm web-filefree sh -lc "cd /app && pnpm -r --if-present format"

format-local: ## Auto-format locally across workspace
	cd apis/filefree && ruff format . && ruff check --fix .
	cd apis/launchfree && ruff format . && ruff check --fix .
	pnpm -r --if-present format

migrate: ## Run database migrations (usage: make migrate API=filefree|launchfree)
	$(COMPOSE) run --rm $(API_SERVICE) alembic upgrade head

migrate-local: ## Run migrations locally (usage: make migrate-local API=filefree|launchfree)
	cd apis/$(API) && alembic upgrade head

migration: ## Create a migration (usage: make migration API=filefree MSG="desc")
	$(COMPOSE) run --rm $(API_SERVICE) alembic revision --autogenerate -m "$(MSG)"

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
	$(COMPOSE) exec $(API_SERVICE) bash

shell-web: ## Open a shell in a web container (default: web-filefree)
	$(COMPOSE) exec $(WEB_SERVICE) sh

db: ## Open psql in shared dev database
	$(COMPOSE) exec postgres psql -U filefree -d filefree_dev

env-pull: ## Pull Vercel production env vars to Studio .env.local
	cd apps/studio && vercel env pull .env.local --environment=production
	@echo "✓ Studio .env.local synced with Vercel production."

env-check: ## Validate env vars across all environments (Vercel, local, Hetzner)
	@bash scripts/env-check.sh

n8n-activate-inactive: ## Activate Agent Thread Handler + CPA Tax Review (needs N8N_API_KEY and N8N_API_URL or N8N_HOST in .env.local)
	@chmod +x scripts/n8n-activate-workflows.sh
	@./scripts/n8n-activate-workflows.sh "Agent Thread Handler" "CPA Tax Review"
