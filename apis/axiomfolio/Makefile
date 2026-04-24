# AxiomFolio — workspace Makefile (monorepo edition).
#
# Dev infrastructure lives at the repo root: infra/compose.dev.yaml boots
# postgres + redis + all product backends + all product frontends in one
# shared stack. See docs/INFRA.md for the architecture.
#
# This Makefile offers AxiomFolio-scoped shortcuts that wrap the root
# compose. Run it from apis/axiomfolio/ (which is where CI invokes it).

.PHONY: up up-ibkr up-tunnel up-ops down down-reset ps logs build health-check \
	test test-shell task-run warm \
	backend-shell \
	migrate-create migrate-up migrate-down migrate-stamp-head \
	frontend-install frontend-lint frontend-typecheck frontend-test frontend-check \
	ladle ladle-build \
	ib-up ib-down ib-logs ib-verify \
	tunnel-up tunnel-down tunnel-logs tunnel-on tunnel-off \
	backup-db restore-db \
	medallion-check medallion-tag medallion-check-sql medallion-lint

# ─── Paths (resolved relative to this file) ───────────────────────────
REPO_ROOT := $(CURDIR)/../..
FRONTEND_DIR := $(REPO_ROOT)/apps/axiomfolio

DOCKER ?= docker
PROJECT ?= paperwork

# Env files (order matters: defaults first, then vault-synced secrets).
ENV_DEFAULTS := $(REPO_ROOT)/infra/env.dev.defaults
ENV_SECRETS  := $(REPO_ROOT)/.env.secrets

# Compose invocations.
COMPOSE      := $(DOCKER) compose --project-name $(PROJECT) -f $(REPO_ROOT)/infra/compose.dev.yaml
COMPOSE_IBKR := $(COMPOSE) -f $(REPO_ROOT)/infra/axiomfolio/compose.profiles.yaml --profile ibkr
COMPOSE_TUN  := $(COMPOSE) -f $(REPO_ROOT)/infra/axiomfolio/compose.profiles.yaml --profile tunnel
COMPOSE_OPS  := $(COMPOSE) -f $(REPO_ROOT)/infra/axiomfolio/compose.profiles.yaml --profile ops
COMPOSE_ALL  := $(COMPOSE) -f $(REPO_ROOT)/infra/axiomfolio/compose.profiles.yaml --profile ibkr --profile tunnel --profile ops

# Axiomfolio service names in the shared compose. Must match Render.
API_SVC          := api-axiomfolio
WORKER_SVC       := celery-axiomfolio-worker
WORKER_HEAVY_SVC := celery-axiomfolio-worker-heavy
BEAT_SVC         := celery-axiomfolio-beat
AXIOMFOLIO_SVCS  := $(API_SVC) $(WORKER_SVC) $(WORKER_HEAVY_SVC) $(BEAT_SVC)

# ─── Default dev stack (shared postgres + redis + all products) ───────
up:
	$(COMPOSE) up -d --build $(AXIOMFOLIO_SVCS)
	@$(MAKE) health-check

up-ibkr: ## Boot axiomfolio + IB Gateway profile
	$(COMPOSE_IBKR) up -d --build $(AXIOMFOLIO_SVCS) ib-gateway
	@$(MAKE) health-check

up-tunnel: ## Boot axiomfolio + Cloudflare tunnel profile
	$(COMPOSE_TUN) up -d --build $(AXIOMFOLIO_SVCS) cloudflared
	@$(MAKE) health-check

up-ops: ## Boot axiomfolio + Flower (Celery task monitor)
	$(COMPOSE_OPS) up -d --build $(AXIOMFOLIO_SVCS) flower
	@$(MAKE) health-check

down:
	$(COMPOSE_ALL) stop $(AXIOMFOLIO_SVCS) ib-gateway cloudflared flower 2>/dev/null; true

down-reset:
	@echo "⚠️  This destroys axiomfolio containers AND shared postgres+redis data."
	@echo "   Other products (filefree/brain/launchfree) will lose their dev DBs."
	@printf "   Type 'yes' to confirm: " && read ans && [ "$$ans" = "yes" ] || (echo "Aborted."; exit 1)
	$(COMPOSE) down -v

ps:
	$(COMPOSE_ALL) ps

logs:
	$(COMPOSE) logs --tail=200 $(AXIOMFOLIO_SVCS)

build:
	$(COMPOSE) build $(AXIOMFOLIO_SVCS)

health-check:
	@./scripts/health_check.sh $(ENV_DEFAULTS)

# ─── Backend shell & task runner ──────────────────────────────────────
backend-shell:
	$(COMPOSE) exec $(API_SVC) bash

# Enqueue a task via Celery (dev). Examples:
#   make task-run TASK=app.tasks.market.coverage.health_check
#   make task-run TASK=app.tasks.market.coverage.daily_bootstrap TASK_KWARGS='{"history_days":5,"history_batch_size":25}'
TASK ?=
TASK_ARGS ?= []
TASK_KWARGS ?= {}
task-run:
	@if [ -z "$(TASK)" ]; then echo "Usage: make task-run TASK=module.task"; exit 2; fi
	$(COMPOSE) exec $(API_SVC) python -m app.scripts.run_task "$(TASK)" --args '$(TASK_ARGS)' --kwargs '$(TASK_KWARGS)'

warm:
	@echo "Queuing nightly pipeline (backfill + indicators + regime + scan)..."
	$(COMPOSE) exec $(API_SVC) python -m app.scripts.run_task "app.tasks.market.coverage.daily_bootstrap" --kwargs '{"history_days":5,"history_batch_size":25}'

# ─── Tests (against axiomfolio_test DB on shared postgres) ────────────
# The test DB is auto-created by infra/init-test-db.sh when postgres first boots.
# This target runs pytest inside the api-axiomfolio container and points
# DATABASE_URL at axiomfolio_test. It NEVER touches axiomfolio_dev.
test:
	$(COMPOSE) up -d postgres redis
	$(COMPOSE) run --rm \
		-e DATABASE_URL=postgresql://paperwork:paperwork_dev@postgres:5432/axiomfolio_test \
		-e REDIS_URL=redis://redis:6379/3 \
		-e CELERY_BROKER_URL=redis://redis:6379/3 \
		-e CELERY_RESULT_BACKEND=redis://redis:6379/3 \
		-e CI=$${CI:-} \
		-e GITHUB_ACTIONS=$${GITHUB_ACTIONS:-} \
		$(API_SVC) python -m pytest -c app/pytest.ini app/tests -v

test-shell:
	$(COMPOSE) run --rm \
		-e DATABASE_URL=postgresql://paperwork:paperwork_dev@postgres:5432/axiomfolio_test \
		-e REDIS_URL=redis://redis:6379/3 \
		$(API_SVC) bash

# ─── Alembic migrations ───────────────────────────────────────────────
MSG ?=
REV ?=
migrate-create:
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-create MSG=\"message\""; exit 2; fi
	$(COMPOSE) exec $(API_SVC) alembic -c app/alembic.ini revision --autogenerate -m "$(MSG)"

migrate-up:
	$(COMPOSE) exec $(API_SVC) alembic -c app/alembic.ini upgrade head

migrate-down:
	@if [ -z "$(REV)" ]; then echo "Usage: make migrate-down REV=<revision|-1>"; exit 2; fi
	$(COMPOSE) exec $(API_SVC) alembic -c app/alembic.ini downgrade "$(REV)"

migrate-stamp-head:
	@echo "WARNING: stamp-head marks the DB as current WITHOUT running migrations."
	@printf "Type 'CONFIRM' to proceed: "; read confirm; [ "$$confirm" = "CONFIRM" ] || { echo "Aborted."; exit 1; }
	$(COMPOSE) exec $(API_SVC) alembic -c app/alembic.ini stamp head

# ─── Frontend (runs host-side via pnpm workspace) ─────────────────────
frontend-install:
	cd $(FRONTEND_DIR) && pnpm install --frozen-lockfile

frontend-lint:
	cd $(FRONTEND_DIR) && pnpm run lint

frontend-typecheck:
	cd $(FRONTEND_DIR) && pnpm run type-check

frontend-test:
	cd $(FRONTEND_DIR) && pnpm run test

frontend-check: frontend-install frontend-lint frontend-typecheck frontend-test

ladle:
	cd $(FRONTEND_DIR) && pnpm run ladle

ladle-build:
	cd $(FRONTEND_DIR) && pnpm run ladle:build

# ─── IB Gateway profile ───────────────────────────────────────────────
ib-up:
	$(COMPOSE_IBKR) up -d ib-gateway

ib-down:
	$(COMPOSE_IBKR) stop ib-gateway

ib-logs:
	$(COMPOSE_IBKR) logs --tail=200 -f ib-gateway

ib-verify: ## Verify IB Gateway connectivity end-to-end
	@echo "Starting IB Gateway..."
	$(COMPOSE_IBKR) up -d ib-gateway
	@echo "Waiting for login (60s timeout)..."
	@for i in $$(seq 1 60); do \
		if $(COMPOSE_IBKR) logs ib-gateway 2>&1 | grep -q "login accepted"; then \
			echo "✓ IB Gateway login accepted"; \
			break; \
		fi; \
		if [ $$i -eq 60 ]; then \
			echo "✗ Timeout waiting for login. Check credentials in .env.secrets"; \
			exit 1; \
		fi; \
		sleep 1; \
	done
	@echo "Checking API connectivity..."
	@curl -sf http://localhost:8004/api/v1/portfolio/options/gateway-status > /dev/null 2>&1 && \
		echo "✓ Gateway API reachable" || \
		echo "⚠ Backend not running or gateway-status endpoint unreachable"

# ─── Cloudflare tunnel profile ────────────────────────────────────────
tunnel-up:
	$(COMPOSE_TUN) up -d cloudflared

tunnel-down:
	$(COMPOSE_TUN) stop cloudflared

tunnel-logs:
	$(COMPOSE_TUN) logs --tail=200 -f cloudflared

tunnel-on: tunnel-up
	@echo "✓ api-dev.axiomfolio.com → local backend. Verify: make tunnel-logs"

tunnel-off: tunnel-down
	@echo "✓ Tunnel stopped (prod api.axiomfolio.com was never affected)"

# ─── DB backup/restore ────────────────────────────────────────────────
backup-db:
	./scripts/backup_db.sh

restore-db:
	@test -n "$(BACKUP)" || (echo "Usage: make restore-db BACKUP=<path/to/dump.sql.gz>"; exit 1)
	./scripts/restore_db.sh "$(BACKUP)"

# ─── Medallion architecture (Wave 0) ──────────────────────────────────
medallion-check:
	@python3 scripts/medallion/check_imports.py --stats

medallion-check-sql:
	@python3 scripts/medallion/check_sql.py --stats

medallion-tag:
	@python3 scripts/medallion/tag_files.py --apply

medallion-lint: medallion-check medallion-check-sql
