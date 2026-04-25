# Medallion tooling (repo-root)

Track D of the Infra & Automation Hardening Sprint lifted the medallion
scripts out of `apis/axiomfolio/scripts/medallion/` into this root directory
so they can be applied to **every** backend that benefits from the layered
architecture (filefree, launchfree, brain, axiomfolio).

## Scripts

| Script | Purpose | Example |
|---|---|---|
| `tag_files.py` | Insert `medallion: <layer>` into module docstrings. Idempotent. | `python scripts/medallion/tag_files.py --app-dir apis/brain --apply` |
| `check_imports.py` | Fail CI when a `silver` file imports `gold`, etc. | `python scripts/medallion/check_imports.py --app-dir apis/axiomfolio` |
| `check_sql.py` | Enforce layer-specific SQL patterns (axiomfolio-only today). | `python scripts/medallion/check_sql.py --app-dir apis/axiomfolio` |

All three scripts read `scripts/medallion/apps.yaml` for per-app
configuration (services root, layer directory map, portfolio splits). Edit
that file once and every backend picks it up — we don't duplicate the map
per project anymore.

## Per-app config

See `scripts/medallion/apps.yaml`:

- `services_root` — path under `--app-dir` that contains the layered code
  (usually `app/services`).
- `import_prefix` — Python module prefix used in `from X import Y` lines.
- `dir_layers` — top-level subdirectory → layer (`bronze`, `silver`,
  `gold`, `execution`, `ops`).
- `portfolio_bronze_patterns` — optional substring patterns that promote
  specific files under a `silver` directory back to `bronze`
  (axiomfolio's broker I/O splits live here).

When a backend has no medallion layers yet (brain, filefree, launchfree),
its entry in `apps.yaml` maps every top-level directory to `ops`. That's
the "safe default" — still enforces the tag exists so future refactors
land somewhere visible.

## CI wiring

`.github/workflows/medallion-lint.yaml` runs `check_imports.py` for each
configured app on every PR that touches its services tree.

## Legacy paths

`apis/axiomfolio/scripts/medallion/*.py` are thin shims that call into the
root-level scripts with `--app-dir apis/axiomfolio` so existing runbooks
and CI references keep working. Remove them once all references are
updated.
