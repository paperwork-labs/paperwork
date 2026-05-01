---
last_reviewed: 2026-05-01
---

# Brain deploy recovery (Render / Postgres / Docker)

**TL;DR:** Merge-time guards for Brain Alembic heads, Dockerfile healthchecks, and import path safety. Read this when Render boot fails after a migration or Dockerfile change.

Operational notes for incidents that surfaced in April 2026 and the guardrails that now block repeats at merge time.

## Regression modes addressed

- **PR #348 — divergent Alembic heads** — parallel quota-monitor migrations reused the same `down_revision`; Alembic reported multiple heads and boot-time upgrades failed (`RuntimeError ... exit code 255`). **Mitigation:** [`scripts/check_alembic_heads.py`](../../scripts/check_alembic_heads.py) walks every `alembic/versions` tree under the repo.
- **PR #352 — Render boot / layout** — Brain cold-start crossed the Docker `HEALTHCHECK --start-period` budget and Render restarted the worker; container layout also invalidated naive `parents[4]` lookups. **Mitigations:**
  - [`scripts/check_dockerfile_healthcheck.py`](../../scripts/check_dockerfile_healthcheck.py) enforces HEALTHCHECK budgets per tracked Dockerfile.
  - [`scripts/check_parents_import_safety.py`](../../scripts/check_parents_import_safety.py) keeps import-time `parents[K]` lookups aligned with `_repo_root()` patterns documented in Brain.

## Guardrail locations

- Workflow runbook path: [.github/workflows/brain-pre-merge-guards.yml](../../.github/workflows/brain-pre-merge-guards.yml)
- Script sources: `scripts/check_alembic_heads.py`, `scripts/check_dockerfile_healthcheck.py`, `scripts/check_parents_import_safety.py`
- Brain overview: [`apis/brain/README.md`](../../apis/brain/README.md)
- **Vercel pre-deploy** (quota + required env vars before production deploy): [PRE_DEPLOY_GUARD.md](PRE_DEPLOY_GUARD.md) and [`scripts/check_pre_deploy.py`](../../scripts/check_pre_deploy.py)

## Local verification (run from repo root)

```bash
python scripts/check_alembic_heads.py &&
python scripts/check_dockerfile_healthcheck.py &&
python scripts/check_parents_import_safety.py
```

All three must pass before merging changes that touch Alembic migrations, Dockerfiles, or Brain path bootstrapping.
