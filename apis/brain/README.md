# Brain service

Runtime code lives under `apis/brain/` (FastAPI worker on Render).

## Pre-merge guards

CI runs three stdlib helpers before pytest where configured (see `.github/workflows/brain-pre-merge-guards.yml`):

| Script | Purpose |
| --- | --- |
| [`scripts/check_alembic_heads.py`](/scripts/check_alembic_heads.py) | Detects divergent Alembic heads per `**/alembic/versions/` tree (#348 quota-monitor collision). |
| [`scripts/check_dockerfile_healthcheck.py`](/scripts/check_dockerfile_healthcheck.py) | Ensures tracked `Dockerfile*` HEALTHCHECK `--start-period` meets per-service floors (Brain boot/regression #352). |
| [`scripts/check_parents_import_safety.py`](/scripts/check_parents_import_safety.py) | Flags brittle `Path(__file__).parents[K]` assignments at Brain module/class scope without mitigations documented in `_repo_root()` patterns (#352). |

Run locally before pushing:

```
python scripts/check_alembic_heads.py &&
python scripts/check_dockerfile_healthcheck.py &&
python scripts/check_parents_import_safety.py
```

If you deliberately need an exception for a Dockerfile change, migrate path, or new `parents` depth, bump the guarded floor **and** the matching script/constants in the same PR, plus a short rationale in the PR body. For `parents[...]` usage, mirror the `_repo_root()`/`REPO_ROOT`/`/app` fallbacks from `apis/brain/app/services/workstreams_loader.py` and extend the checker only when the mitigation pattern is repeatable.
