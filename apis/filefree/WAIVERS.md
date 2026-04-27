# FileFree API — Medallion Phase 0.D waivers

Tracked suppressions for strict Ruff / mypy. Re-audit when upgrading dependencies.

| Location | Kind | Reason |
|----------|------|--------|
| `app/redis.py` | `# type: ignore[attr-defined]` on `aclose` | `redis` stubs omit async `aclose`; runtime `redis.asyncio` client supports it. |
| `app/main.py` | `# type: ignore[arg-type]` on `RateLimitExceeded` handler | `slowapi` handler signature is narrower than Starlette’s `Exception` handler union. |
| `pyproject.toml` — `per-file-ignores` | `B008` on `app/dependencies.py` | FastAPI `Depends()` in dependency parameters (framework pattern). |
| `pyproject.toml` — `per-file-ignores` | `B008`, `ARG001` on `app/routers/**` | FastAPI DI (`Depends`) and request parameters reserved for future use / limiter. |

**CI scope:** `mypy app` (application package only; tests use relaxed `[[tool.mypy.overrides]]` in `pyproject.toml`).
