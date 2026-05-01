# pwl CLI Runbook

**TL;DR:** Operator commands for listing apps, doctor checks, scaffolding APIs, and rebuilding `app_registry.json`. Open when you onboard a service or refresh the manifest.

`pwl` is the Paperwork Labs monorepo CLI. It gives operators one place to inspect apps, scaffold new services, and keep Brain's app manifest current.

## Commands

- `pwl version` prints the installed CLI version.
- `pwl list-apps` lists apps, APIs, and packages with language and freshness metadata.
- `pwl doctor` checks local monorepo tooling and health markers.
- `pwl new-app <name> --type api` scaffolds a new FastAPI service from the maintained template.
- `pwl onboard <app-path>` audits an existing app for framework and template conformance.
- `pwl registry-build` rebuilds Brain's app registry at `apis/brain/data/app_registry.json`.

## Onboard An Existing App

Run:

```bash
cd tools/pwl
uv run pwl onboard apis/brain
```

The report starts with the detected app type, framework, language, and conformance score, then prints:

```markdown
| marker | required | present | gap |
| --- | --- | --- | --- |
```

`present=no` rows are the follow-up work. The command exits `0` only when every required marker is present; otherwise it exits `1` and lists the gaps below the table.

## Rebuild Brain's Registry

Run:

```bash
cd tools/pwl
uv run pwl registry-build
```

The command walks `apis/*`, `apps/*`, `packages/*`, and `tools/*`, detects each app's framework, deployment target, service dependencies, size signals, and conformance markers, then overwrites `apis/brain/data/app_registry.json`.

Brain reads this manifest through `apis/brain/app/services/app_registry.py` for systemwide ops decisions and admin reporting. Re-run `pwl registry-build` whenever apps are added, retired, renamed, or brought into conformance.
