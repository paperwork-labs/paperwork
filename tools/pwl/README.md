# pwl

`pwl` is the Paperwork Labs CLI for scaffolding new apps and auditing monorepo health. WS-58 delivers the command shell, health checks, app inventory, and a `new-app` stub; WS-59 fills in template rendering; WS-60 uses those templates to onboard existing apps.

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
- `pwl new-app <name> [--type api|web|package] [--language python|typescript]` previews the L4 handoff flow that WS-59 will implement.

## Workstreams

- `WS-58-pwl-cli`: CLI scaffold and skeleton subcommands.
- `WS-59-template-authoring-kit`: template rendering and authoring workflow.
- `WS-60-onboard-existing-apps-to-templates`: migrate current apps into the template system.
