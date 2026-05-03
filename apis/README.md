# Paperwork Labs — Python Backends

Four FastAPI backends, one per product, share a single uv workspace at the
monorepo root.

| Backend | Product | Notes |
|---|---|---|
| `axiomfolio/` | AxiomFolio (portfolio + trading) | Has its own MCP server; reference implementation extracted into `packages/python/mcp-server/` (Wave K2) |
| `brain/` | Brain (curated agent OS) | The internal control plane; registers all product MCP servers |
| `filefree/` | FileFree (multi-state tax filing) | Will adopt `packages/python/mcp-server/` in Wave K11 |
| `launchfree/` | LaunchFree (formation + filing automation) | Will adopt `packages/python/mcp-server/` in Wave K12 |

## Workspace layout

The monorepo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
defined at the root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = ["apis/*", "packages/python/*"]
```

Every backend in `apis/<name>/` and every shared package in
`packages/python/<name>/` is a workspace member with its own `pyproject.toml`.
Workspace members can depend on each other via the `[tool.uv.sources]` table:

```toml
[project]
dependencies = ["mcp-server", "fastapi==0.136.1", ...]

[tool.uv.sources]
mcp-server = { workspace = true }
```

## Common workflow

From the monorepo root:

```bash
# Resolve + install everything in the workspace into a single venv at .venv/
uv sync

# Add a workspace dep to a backend (writes to its pyproject.toml)
uv add --package axiomfolio mcp-server

# Run a backend's test suite
uv run --package axiomfolio pytest apis/axiomfolio/app/tests/

# Run a shared package's test suite
uv run --package mcp-server pytest packages/python/mcp-server/tests/

# Verify the lockfile is up to date (CI)
uv lock --check
```

## Production deploys still use pip + requirements.txt

Each backend's `Dockerfile` continues to use `pip install -r requirements.txt`
(plus a separate `pip install` for shared workspace packages copied from
`packages/python/`). The uv workspace is for *local development and CI*;
production images are unchanged. This is intentional — the migration to a
fully uv-driven build is a separate, riskier change deferred to a later wave.

The key consequence: **`requirements.txt` is still the source of truth for
runtime deps** in each backend. The backend's `pyproject.toml` declares only
workspace deps (e.g. `mcp-server`) and tooling configuration (ruff, mypy, etc.).
PyPI deps are NOT duplicated into both files.

## CI

The platform CI runs `uv lock --check` and `uv sync --frozen` in addition to
the per-backend `pip install -r requirements.txt` so that drift between the
two is caught early. uv is pinned to the version recorded in
`.github/workflows/python-ci.yml`.

See [`packages/python/README.md`](../packages/python/README.md) for the
shared-package authoring guide.
