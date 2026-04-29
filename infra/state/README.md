# Canonical Infra State

`infra/state/*.yaml` files are Brain's canonical record for externally managed infrastructure. The drift detector compares these files against live provider APIs every 30 minutes and records each run under `apis/brain/data/`.

The canonical file wins for UI-only or cosmetic edits. Those changes can be reconciled silently on the next pass because they do not change runtime behavior.

Semantic drift is different: new or removed environment variables, DNS record changes, service additions, and provider configuration changes should not be auto-reverted. Brain records an open drift alert, emits a critical log line for `#brain-status`, and a follow-up reconcile PR updates the canonical state after review.

## Surfaces

- `vercel.yaml` — Vercel project environment variables and config.
- `cloudflare.yaml` — Cloudflare DNS records per zone.
- `render.yaml` — Render environment variables per service.
- `clerk.yaml` — Clerk domain configuration.

## Reconcile Flow

1. Seed an initial baseline from live state, for example `python3 scripts/iac_drift_seed.py vercel`.
2. Review the generated canonical YAML before merging.
3. Brain runs the drift check every 30 minutes.
4. Semantic drift opens an alert and should become a reconcile PR.
5. When the reconcile PR merges, close the matching alert entry.
