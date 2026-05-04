# Brain deploy stability gate (T3.7)

Operational definition of “green” for Brain API deploy stability and how to rerun checks manually.

## What “green” means

1. **Host deploy succeeded** — Your deployment platform marks the `brain-api` service live on the intended revision (e.g. Render deploy finished without rollback).
2. **GitHub Actions — Brain deploy smoke gate** — Workflow `.github/workflows/brain-deploy-smoke.yaml` completes successfully:
   - **Pytest smoke** — `pytest apis/brain/tests/test_*smoke*` passes on `ubuntu-latest`.
   - **Live smoke** — `python apis/brain/scripts/post_deploy_smoke.py --ci --report-conversation` exits `0` on the self-hosted runner.

The smoke script is **fail-closed**: exit code `1` (required checks failed) or `2` (optional HTTP probes failed) fails the workflow. There is no `continue-on-error` path.

### Required vs optional probes (live smoke)

See `apis/brain/scripts/post_deploy_smoke.py` and `docs/infra/BRAIN_SCHEDULER.md` (Post-deploy smoke). In short:

- **Required**: `GET /health` with expected envelope; database read of `agent_dispatches`.
- **Optional HTTP**: `/health/deep`, `/internal/schedulers` — failures still yield **non-zero exit** and fail CI.

## Five consecutive green deploys

Track this outside this file (e.g. deploy dashboard history + Actions run list):

- Count only deploys where both the **platform deploy** and the **Brain deploy smoke gate** run for that promotion succeeded.
- Reset the counter on any red deploy or skipped smoke for a production promotion.

## Manual rerun

1. Open **Actions** → **Brain deploy smoke gate** → **Run workflow**.
2. Run on the default branch (or the branch you intend to validate).
3. Ensure repository secrets **`BRAIN_API_URL`** and (for failure alerts) **`BRAIN_ADMIN_TOKEN`** are set; the live job runs on `[self-hosted, hetzner]` and relies on the same database connectivity profile as other Brain CI jobs.

## Automation trigger (optional)

To run smoke automatically after deploy, send a **`repository_dispatch`** with type **`brain-deploy-completed`** to this repository (configure in your hosting provider or orchestration; do not embed URLs or tokens in this doc).

## Related

- `docs/infra/BRAIN_SCHEDULER.md` — smoke script behavior and exit codes.
- `apis/brain/scripts/post_deploy_smoke.py` — implementation.
