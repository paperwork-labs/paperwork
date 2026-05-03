# Paperwork Labs — Shared Python Packages

This directory holds **shared Python infrastructure** that's reused across the
four FastAPI backends (`apis/axiomfolio`, `apis/brain`, `apis/filefree`,
`apis/launchfree`). Each subdirectory is a standalone, editable-installable
Python package wired into the monorepo via [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/).

> **Why this exists:** before this layout, every backend had its own copy of
> the same building blocks (MCP server, money helpers, Clerk auth, structured
> logging, rate-limit wrappers). Drift across copies has caused real bugs (see
> Wave K3 in `.cursor/plans/plan_1a0d246a.plan.md` for the canonical case —
> duplicated tax tables in FileFree). Extracting once and consuming everywhere
> kills that whole class of problem at the source.

## Layout convention

```
packages/python/<name>/
├── pyproject.toml              # [project] metadata + deps + workspace dep declarations
├── README.md                   # how to use the package; minimum a 20-line consumer example
├── src/<name_underscored>/     # source root (`src/`-layout, NOT a flat package at the root)
│   ├── __init__.py             # re-export the public API; everything else is private
│   └── ...
└── tests/                      # pytest suite; >= 80% coverage of the public surface
```

Two rules:

1. **Use the `src/`-layout.** It prevents accidental imports of test fixtures
   into product code and matches every other Python package in the monorepo.
2. **Module name is the package name with hyphens replaced by underscores.**
   So `packages/python/mcp-server/` exposes `import mcp_server`.

## Adding a new package

1. Create the directory tree above. Pick a kebab-case package name and the
   matching snake-case module name.
2. Write a minimal `pyproject.toml`:
   ```toml
   [project]
   name = "<package-name>"
   version = "0.0.0"
   description = "<one line>"
   requires-python = ">=3.11"
   dependencies = ["<runtime deps>"]

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [tool.hatch.build.targets.wheel]
   packages = ["src/<module_name>"]
   ```
3. From the monorepo root, run `uv sync`. The package is now editable-installed
   in the workspace virtualenv and importable from any other workspace member.
4. Write tests under `tests/` and run `uv run --package <package-name> pytest`.

That's it — no central registry to update. The root `pyproject.toml` discovers
new members via `members = ["apis/*", "packages/python/*"]`.

## How backends consume shared packages

Inside a backend's `pyproject.toml` (e.g. `apis/axiomfolio/pyproject.toml`):

```toml
[project]
name = "axiomfolio"
# ...
dependencies = [
  "mcp-server",   # workspace dep
  "fastapi==0.136.1",
  # ...
]

[tool.uv.sources]
mcp-server = { workspace = true }
```

The `[tool.uv.sources]` table is what tells uv "resolve `mcp-server` from the
local workspace, not PyPI". Without it, uv would try to download a
hypothetical PyPI release.

For Docker / production builds, the consumer's `Dockerfile` copies the package
directory in and `pip install`s it directly (mirrors how `packages/auth-clerk/`
is consumed today):

```dockerfile
COPY packages/python/mcp-server /tmp/mcp-server
RUN pip install --no-cache-dir /tmp/mcp-server
```

## Why uv workspaces (vs. `pip install -e ../shared/`)

* **One lockfile** at the root pins every transitive dependency across all 4
  backends + N shared packages. `uv lock --check` in CI catches drift.
* **No `PYTHONPATH` hacks** — every workspace member is properly installed
  into the workspace venv.
* **Fast.** `uv sync` resolves and installs the entire monorepo in seconds
  thanks to the Rust resolver and the global package cache.
* **Familiar to JS folks.** The TS workspace at the monorepo root works the
  same way (`pnpm workspaces` -> `uv workspaces`), so the mental model
  transfers cleanly.

## Current packages

| Package | Status | Purpose |
|---|---|---|
| `mcp-server` | Live (Wave K2) | JSON-RPC 2.0 dispatcher + bearer-token auth + per-user daily quota for product MCP servers (AxiomFolio, FileFree, LaunchFree) |

Future packages (Wave K3+, separate PRs): `data-engine`, `api-foundation`,
`clerk-auth`, `money`, `observability`, `rate-limit`, `pii-scrubber`. See
`.cursor/plans/plan_1a0d246a.plan.md` for the full roadmap.
