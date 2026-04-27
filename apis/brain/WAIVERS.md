# Brain API — Medallion Phase 0.D waivers

## Ruff

| Item | Reason |
|------|--------|
| `ignore = ["PTH"]` in `pyproject.toml` | Broad `os.path` usage in tools/ingestion; migrating to `pathlib` is mechanical follow-up (no behavior change intended in 0.D). |
| `per-file-ignores` for `app/routers/**`, `app/dependencies.py` | FastAPI `Depends()` / DI patterns (`B008`, `ARG001`). |

## Mypy

| Item | Reason |
|------|--------|
| `ignore_missing_imports = true` | Optional third-party packages (tiktoken, langfuse, apscheduler, etc.) lack complete stubs in CI. |
| `[[tool.mypy.overrides]]` + `ignore_errors = true` for **27 legacy modules** | Full strict drain on `llm`, `admin`, schedulers, tools, etc. is tracked for a follow-up; new code should land in typed modules or add explicit annotations. See the `module = [...]` list in `pyproject.toml` under *Medallion 0.D*. |
| `app.models.*` — `disallow_any_generics = false` | JSONB columns use plain `dict` / `list` until TypedDict models exist. |

## CI

- `ruff check` + `ruff format --check` + `mypy app --config-file ./pyproject.toml` + `pytest` (see `.github/workflows/ci.yaml` `brain-test`).
