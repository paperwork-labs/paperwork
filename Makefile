.PHONY: up up-all down down-reset ps logs build health-check ladle-up ladle-down ladle-logs ladle-build \
	test-up test test-frontend test-all test-down \
	backend-shell frontend-shell task-run \
	migrate-create migrate-up migrate-down migrate-stamp-head \
	frontend-install frontend-lint frontend-typecheck frontend-test frontend-check \
	ib-up ib-down ib-logs ib-verify \
	tunnel-up tunnel-down tunnel-logs tunnel-on tunnel-off

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
	$(COMPOSE_DEV_UI) up -d --build
	$(MAKE) health-check

up-all:
	$(COMPOSE_DEV_ALL) up -d --build
	$(MAKE) health-check

down:
	@# Restore prod DNS if tunnel was running (idempotent -- safe if tunnel was off)
	@if docker ps --format '{{.Names}}' 2>/dev/null | grep -q axiomfolio-cloudflared; then \
		$(MAKE) tunnel-off; \
	fi
	$(COMPOSE_DEV_ALL) down

down-reset:
	@echo "⚠️  WARNING: This will DELETE ALL DATA including the PostgreSQL database, Redis, and all volumes."
	@echo "   This action is IRREVERSIBLE."
	@printf "   Type 'yes' to confirm: " && read ans && [ "$$ans" = "yes" ] || (echo "Aborted."; exit 1)
	@if docker ps --format '{{.Names}}' 2>/dev/null | grep -q axiomfolio-cloudflared; then \
		$(MAKE) tunnel-off; \
	fi
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
# make task-run TASK=backend.tasks.market_data_tasks.monitor_coverage_health
# make task-run TASK=backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked TASK_KWARGS='{"history_days":5,"history_batch_size":25}'
TASK ?=
TASK_ARGS ?= []
TASK_KWARGS ?= {}
task-run:
	@if [ -z "$(TASK)" ]; then echo "Usage: make task-run TASK=module.task"; exit 2; fi
	$(COMPOSE_DEV) exec backend python -m backend.scripts.run_task "$(TASK)" --args '$(TASK_ARGS)' --kwargs '$(TASK_KWARGS)'

# IB Gateway (requires IBKR_USERNAME and IBKR_PASSWORD in env.dev)
ib-up:
	$(COMPOSE_DEV_IBKR) up -d ib-gateway

ib-down:
	$(COMPOSE_DEV_IBKR) stop ib-gateway

ib-logs:
	$(COMPOSE_DEV_IBKR) logs --tail=200 -f ib-gateway

# Cloudflare Tunnel (routes api.axiomfolio.com to local backend for OAuth testing)
tunnel-up:
	$(COMPOSE_DEV_TUNNEL) up -d cloudflared

tunnel-down:
	$(COMPOSE_DEV_TUNNEL) stop cloudflared

tunnel-logs:
	$(COMPOSE_DEV_TUNNEL) logs --tail=200 -f cloudflared

# One-command dev OAuth: delete prod CNAME, start tunnel, api.axiomfolio.com → local backend
# Reads CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID from env.dev
tunnel-on:
	$(eval include $(ENV_DEV))
	$(eval export CLOUDFLARE_API_TOKEN CLOUDFLARE_ZONE_ID)
	@test -n "$(CLOUDFLARE_API_TOKEN)" || (echo "ERROR: CLOUDFLARE_API_TOKEN not set in $(ENV_DEV)"; exit 1)
	@test -n "$(CLOUDFLARE_ZONE_ID)" || (echo "ERROR: CLOUDFLARE_ZONE_ID not set in $(ENV_DEV)"; exit 1)
	@echo "Deleting api CNAME (prod → Render)..."
	@RECORD_ID=$$(curl -s "https://api.cloudflare.com/client/v4/zones/$(CLOUDFLARE_ZONE_ID)/dns_records?name=api.axiomfolio.com" \
		-H "Authorization: Bearer $(CLOUDFLARE_API_TOKEN)" | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print(r[0]['id'] if r else '')"); \
	if [ -n "$$RECORD_ID" ]; then \
		curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$(CLOUDFLARE_ZONE_ID)/dns_records/$$RECORD_ID" \
			-H "Authorization: Bearer $(CLOUDFLARE_API_TOKEN)" | python3 -c "import json,sys; d=json.load(sys.stdin); print('✓ CNAME deleted' if d.get('success') else f'✗ {d}')"; \
	else \
		echo "No api CNAME found (tunnel may already own the hostname)"; \
	fi
	@echo "Starting tunnel..."
	$(COMPOSE_DEV_TUNNEL) up -d cloudflared
	@echo "✓ api.axiomfolio.com → local backend. Verify: make tunnel-logs"

# Restore prod: stop tunnel, delete tunnel CNAME, recreate CNAME api → Render
tunnel-off:
	$(eval include $(ENV_DEV))
	$(eval export CLOUDFLARE_API_TOKEN CLOUDFLARE_ZONE_ID)
	@test -n "$(CLOUDFLARE_API_TOKEN)" || (echo "ERROR: CLOUDFLARE_API_TOKEN not set in $(ENV_DEV)"; exit 1)
	@test -n "$(CLOUDFLARE_ZONE_ID)" || (echo "ERROR: CLOUDFLARE_ZONE_ID not set in $(ENV_DEV)"; exit 1)
	@echo "Stopping tunnel..."
	-$(COMPOSE_DEV_TUNNEL) stop cloudflared
	@echo "Restoring api CNAME → Render..."
	@RECORD_ID=$$(curl -s "https://api.cloudflare.com/client/v4/zones/$(CLOUDFLARE_ZONE_ID)/dns_records?name=api.axiomfolio.com" \
		-H "Authorization: Bearer $(CLOUDFLARE_API_TOKEN)" | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print(r[0]['id'] if r else '')"); \
	if [ -n "$$RECORD_ID" ]; then \
		curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$(CLOUDFLARE_ZONE_ID)/dns_records/$$RECORD_ID" \
			-H "Authorization: Bearer $(CLOUDFLARE_API_TOKEN)" > /dev/null; \
	fi
	@curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$(CLOUDFLARE_ZONE_ID)/dns_records" \
		-H "Authorization: Bearer $(CLOUDFLARE_API_TOKEN)" \
		-H "Content-Type: application/json" \
		-d '{"type":"CNAME","name":"api","content":"axiomfolio-api.onrender.com","proxied":true,"ttl":1}' \
		| python3 -c "import json,sys; d=json.load(sys.stdin); print('✓ CNAME restored → Render' if d.get('success') else f'✗ {d}')"
	@echo "✓ api.axiomfolio.com → Render (prod)"

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

