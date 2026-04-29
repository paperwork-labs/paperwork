# pwl

`pwl` is the Paperwork Labs CLI for scaffolding new apps and auditing monorepo health. WS-58 delivered the command shell, health checks, and app inventory; WS-59 makes `new-app --type api` render a real FastAPI scaffold; WS-60 adds web templates and existing-app onboarding.

## Install

```bash
uv pip install -e tools/pwl
```

For development:

```bash
cd tools/pwl
uv sync
uv run pwl --help
```

## Commands

- `pwl version` prints the CLI version and current git short SHA.
- `pwl list-apps` lists `apis/*`, `apps/*`, and `packages/*` entries with type, language, and last-commit freshness.
- `pwl doctor` checks that the current tree is a Paperwork monorepo, required CLIs are available, env examples exist, and the merge queue is empty.
- `pwl new-app <name> --type api [--dry-run]` creates a FastAPI service in `apis/<name>/`, appends a Render service, and adds a Studio onboarding workstream.

## Workstreams

- `WS-58-pwl-cli`: CLI scaffold and skeleton subcommands.
- `WS-59-template-authoring-kit`: API template rendering and authoring workflow.
- `WS-60-onboard-existing-apps-to-templates`: migrate current apps into the template system.
