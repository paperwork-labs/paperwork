.PHONY: up up-all down down-reset ps logs build health-check warm ladle-up ladle-down ladle-logs ladle-build \
	test-up test-syntax test test-frontend test-all test-down \
	backend-shell frontend-shell task-run \
	migrate-create migrate-up migrate-down migrate-stamp-head \
	frontend-install frontend-lint frontend-typecheck frontend-test frontend-check \
	ib-up ib-down ib-logs ib-verify \
	tunnel-up tunnel-down tunnel-logs tunnel-on tunnel-off \
	backup-db \
	medallion-check medallion-tag

DOCKER ?= docker
PROJECT ?= axiomfolio
PROJECT_TEST ?= axiomfolio_test

ENV_DEV ?= infra/env.dev
ENV_TEST ?= infra/env.test

COMPOSE_DEV = $(DOCKER) compose --project-name $(PROJECT) --env-file $(ENV_DEV) -f infra/compose.dev.yaml
COMPOSE_DEV_UI = $(DOCKER) compose --project-name $(PROJECT) --env-file $(ENV_DEV) -f infra/compose.dev.yaml --profile ui
COMPOSE_DEV_IBKR = $(DOCKER) compose --project-name $(PROJECT) --env-file $(ENV_DEV) -f infra/compose.dev.yaml --profile ibkr
COMPOSE_DEV_TUNNEL = $(DOCKER) compose --project-name $(PROJECT) --env-file $(ENV_DEV) -f infra/compose.dev.yaml --profile tunnel
COMPOSE_DEV_ALL = $(DOCKER) compose --project-name $(PROJECT) --env-file $(ENV_DEV) -f infra/compose.dev.yaml --profile ui --profile ibkr --profile tunnel
COMPOSE_TEST = $(DOCKER) compose --project-name $(PROJECT_TEST) --env-file $(ENV_TEST) -f infra/compose.test.yaml

up:
	$(COMPOSE_DEV_ALL) up -d --build
	$(MAKE) health-check

up-ui:
	$(COMPOSE_DEV_UI) up -d --build
	$(MAKE) health-check

down:
	$(COMPOSE_DEV_ALL) down

down-reset:
	@echo "⚠️  WARNING: This will DELETE ALL DATA including the PostgreSQL database, Redis, and all volumes."
	@echo "   This action is IRREVERSIBLE."
	@printf "   Type 'yes' to confirm: " && read ans && [ "$$ans" = "yes" ] || (echo "Aborted."; exit 1)
	$(COMPOSE_DEV_ALL) down -v

ps:
	$(COMPOSE_DEV_UI) ps

logs:
	$(COMPOSE_DEV_UI) logs --tail=200 backend celery_worker celery_beat frontend ladle

build:
	$(COMPOSE_DEV_UI) build

health-check:
	./scripts/health_check.sh $(ENV_DEV)

ladle-up:
	$(COMPOSE_DEV_UI) up -d --build ladle

ladle-down:
	$(COMPOSE_DEV_UI) down

ladle-logs:
	$(COMPOSE_DEV_UI) logs --tail=200 ladle

ladle-build:
	$(COMPOSE_DEV_UI) run --rm ladle npm run ladle:build --silent

test-up:
	$(COMPOSE_TEST) up -d postgres_test redis_test

# Check all backend Python files for syntax errors (SyntaxError/IndentationError).
# Uses ast.parse() to avoid writing .pyc/__pycache__ (fails in Docker as non-root).
test-syntax:
	$(COMPOSE_TEST) run --rm backend_test python scripts/check_syntax.py

test:
	@# Always use a fresh isolated test DB volume to prevent migration drift.
	@# This never touches dev DB; it only resets the axiomfolio_test project volumes.
	-$(COMPOSE_TEST) down -v
	$(COMPOSE_TEST) up -d postgres_test redis_test
	$(COMPOSE_TEST) run --rm backend_test
	$(COMPOSE_TEST) down -v

test-frontend: frontend-check

# Run both suites
test-all: test test-frontend

test-down:
	$(COMPOSE_TEST) down -v

backend-shell:
	$(COMPOSE_DEV) exec backend bash

frontend-shell:
	$(COMPOSE_DEV) exec frontend sh

# Alembic migrations (dev DB only; tests run migrations against postgres_test via pytest)
# Usage:
# - make migrate-create MSG="add foo table"
# - make migrate-up
# - make migrate-down REV=-1
# - make migrate-stamp-head
MSG ?=
REV ?=
migrate-create:
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-create MSG=\"message\""; exit 2; fi
	$(COMPOSE_DEV) exec backend alembic -c backend/alembic.ini revision --autogenerate -m "$(MSG)"

migrate-up:
	$(COMPOSE_DEV) exec backend alembic -c backend/alembic.ini upgrade head

migrate-down:
	@if [ -z "$(REV)" ]; then echo "Usage: make migrate-down REV=<revision| -1>"; exit 2; fi
	$(COMPOSE_DEV) exec backend alembic -c backend/alembic.ini downgrade "$(REV)"

migrate-stamp-head:
	@echo "WARNING: stamp-head marks the DB as current WITHOUT running migrations."
	@echo "This is destructive and should only be used during initial provisioning."
	@printf "Type 'CONFIRM' to proceed: "; read confirm; [ "$$confirm" = "CONFIRM" ] || { echo "Aborted."; exit 1; }
	$(COMPOSE_DEV) exec backend alembic -c backend/alembic.ini stamp head

frontend-install:
	$(COMPOSE_DEV) exec -T frontend npm ci

frontend-lint:
	$(COMPOSE_DEV) exec -T frontend npm run lint

frontend-typecheck:
	$(COMPOSE_DEV) exec -T frontend npm run type-check

frontend-test:
	$(COMPOSE_DEV) exec -T frontend npm run test

frontend-check: frontend-install frontend-lint frontend-typecheck frontend-test

# Enqueue a task via Celery (dev). Example:
# make task-run TASK=backend.tasks.market.coverage.health_check
# make task-run TASK=backend.tasks.market.coverage.daily_bootstrap TASK_KWARGS='{"history_days":5,"history_batch_size":25}'
TASK ?=
TASK_ARGS ?= []
TASK_KWARGS ?= {}
task-run:
	@if [ -z "$(TASK)" ]; then echo "Usage: make task-run TASK=module.task"; exit 2; fi
	$(COMPOSE_DEV) exec backend python -m backend.scripts.run_task "$(TASK)" --args '$(TASK_ARGS)' --kwargs '$(TASK_KWARGS)'

warm:
	@echo "Queuing nightly pipeline (backfill + indicators + regime + scan)..."
	$(COMPOSE_DEV) exec backend python -m backend.scripts.run_task "backend.tasks.market.coverage.daily_bootstrap" --kwargs '{"history_days":5,"history_batch_size":25}'

# IB Gateway (requires IBKR_USERNAME and IBKR_PASSWORD in env.dev)
ib-up:
	$(COMPOSE_DEV_IBKR) up -d ib-gateway

ib-down:
	$(COMPOSE_DEV_IBKR) stop ib-gateway

ib-logs:
	$(COMPOSE_DEV_IBKR) logs --tail=200 -f ib-gateway

# Cloudflare Tunnel (routes api-dev.axiomfolio.com to local backend for OAuth testing)
# Uses a dedicated dev subdomain so production (api.axiomfolio.com) is never affected.
# Prereq: Cloudflare Zero Trust tunnel public hostname must be set to api-dev.axiomfolio.com
tunnel-up:
	$(COMPOSE_DEV_TUNNEL) up -d cloudflared

tunnel-down:
	$(COMPOSE_DEV_TUNNEL) stop cloudflared

tunnel-logs:
	$(COMPOSE_DEV_TUNNEL) logs --tail=200 -f cloudflared

backup-db:
	./scripts/backup_db.sh

restore-db:
	@echo "Usage: make restore-db BACKUP=~/axiomfolio-backups/axiomfolio_YYYYMMDD_HHMMSS.sql.gz"
	@test -n "$(BACKUP)" || (echo "ERROR: Set BACKUP=<path>"; exit 1)
	./scripts/restore_db.sh "$(BACKUP)"

tunnel-on: tunnel-up
	@echo "✓ api-dev.axiomfolio.com → local backend:8000. Verify: make tunnel-logs"

tunnel-off: tunnel-down
	@echo "✓ Tunnel stopped (prod api.axiomfolio.com was never affected)"

ib-verify: ## Verify IB Gateway connectivity end-to-end
	@echo "Starting IB Gateway..."
	docker compose -f infra/compose.dev.yaml --profile ib up -d ib-gateway
	@echo "Waiting for login (60s timeout)..."
	@for i in $$(seq 1 60); do \
		if docker compose -f infra/compose.dev.yaml logs ib-gateway 2>&1 | grep -q "login accepted"; then \
			echo "✓ IB Gateway login accepted"; \
			break; \
		fi; \
		if [ $$i -eq 60 ]; then \
			echo "✗ Timeout waiting for login. Check credentials in infra/env.dev"; \
			echo "  Logs: docker compose -f infra/compose.dev.yaml logs ib-gateway"; \
			exit 1; \
		fi; \
		sleep 1; \
	done
	@echo "Checking API connectivity..."
	@curl -sf http://localhost:8000/api/v1/portfolio/options/gateway-status > /dev/null 2>&1 && \
		echo "✓ Gateway API reachable" || \
		echo "⚠ Backend not running or gateway-status endpoint unreachable (start backend first)"


# ---------- Medallion architecture (Wave 0) ----------

medallion-check:
	@python3 scripts/medallion/check_imports.py --stats

medallion-tag:
	@python3 scripts/medallion/tag_files.py --apply
