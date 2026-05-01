---
owner: engineering
last_reviewed: 2026-04-23
doc_kind: philosophy
domain: data
status: active
---

# Data Philosophy

Immutable rules for how Paperwork Labs handles data — from broker ingest to LLM context to user PII. Edits require founder + `engineering` persona ack.

Companions: [`docs/axiomfolio/MARKET_DATA.md`](../axiomfolio/MARKET_DATA.md) (mutable "how" for trading data) and [`docs/INFRA.md`](../INFRA.md) for storage layout.

## 1. Medallion iron laws

Every data path is classified into one of four layers (`bronze`, `silver`, `gold`, `ops`). The lint at `scripts/medallion/check_imports.py` enforces them. The laws below are immutable:

1. **Bronze** = raw ingest. Append-only, no mutations. A bronze row written today must be re-readable identically forever (modulo schema migrations that are additive, never destructive).
2. **Silver** = cleaned, deduplicated, joined. Silver may rewrite history if and only if a bronze row changed (e.g. broker correction). Silver writes are idempotent on `(bronze_id, transform_version)`.
3. **Gold** = analytics-ready, materialized for the UI. Gold may be torn down and rebuilt from silver at any time.
4. **Ops** = operational metadata (job runs, alerts, costs). Independent of the bronze→silver→gold chain.

Violations:

- Bronze importing from silver/gold/ops → **forbidden** (lint catches)
- Silver mutating bronze → **forbidden** (DB-level CHECK constraint or trigger)
- Gold being the system of record for anything → **forbidden** (gold is rebuildable, period)

## 2. Source of truth (SoT) hierarchy

When two sources conflict, the higher layer wins. The hierarchy:

| Layer                           | Examples                                              | Wins when conflicting with                          |
|---------------------------------|-------------------------------------------------------|-----------------------------------------------------|
| Broker / IRS / state filing API | IBKR, Plaid, MeF                                      | everything below                                    |
| Bronze table                    | `bronze.broker_positions`, `bronze.market_quotes_raw` | silver, gold, app cache                             |
| Silver table                    | `silver.positions`, `silver.market_quotes_clean`      | gold, app cache                                     |
| Gold materialization            | `gold.portfolio_snapshot`, dashboard rollups          | app cache only                                      |
| App-level cache                 | Redis, in-memory                                      | nothing — cache is invalidated, never authoritative |

When in doubt, **re-fetch from the highest layer that owns the field**. Never paper over a discrepancy with a manual UPDATE — it'll come back.

## 3. Append-only ledgers

These tables are **append-only** and protected by both lint and DB triggers:

- `bronze.broker_*` — every ingest cycle appends
- `bronze.market_quotes_raw` — every fetch appends
- `bronze.tax_lots_raw` — every broker statement appends
- `ops.cost_ledger` — every LLM call appends
- `ops.audit_log` — every persona invocation appends
- `ops.tool_call_audit` — every tool call appends

If a row needs to be "deleted," it gets a soft-delete with a `superseded_at` timestamp pointing to the row that replaced it. The original row is never updated or removed.

## 4. PII handling

PII is anything in the union of:

- Government IDs (SSN, ITIN, EIN, broker account numbers)
- Financial account numbers (bank, broker, card)
- Real names paired with any financial figure
- Email + phone paired with any financial action

Rules:

1. PII at rest is encrypted using the per-user Fernet key (`apis/axiomfolio/app/services/encryption.py`). The key is rotated annually per `docs/axiomfolio/ENCRYPTION_KEY_ROTATION.md`.
2. PII in logs is forbidden. The `redact_credentials` log filter is mandatory; `apis/brain` and `apis/axiomfolio` CI fails if a service binds without it.
3. PII never leaves Render Postgres (or its Neon branches) except via:
   - Authenticated read by the user themselves (their session)
   - The user's broker / IRS / state portal (the same data they sent us)
   - An approved sub-processor (see `docs/axiomfolio/privacy.md`)
4. PII in LLM prompts goes through `app/services/pii_scrubber.py` first. Replacements are reversible per-session via the scrubber's mapping table; cross-session reversal is forbidden.
5. PII retention default is **18 months past last user activity**. Tax-related PII follows IRS retention rules (7 years). User-initiated deletion (GDPR / CCPA) is honored within 30 days.

## 5. When pipelines must HALT vs DEGRADE

Defaults:

- A bronze ingest failure HALTS the dependent silver build for that source. Silver runs on the previous bronze snapshot. Stale data is preferred over wrong data.
- A silver build failure HALTS the dependent gold materialization. The UI shows the gold "as of" timestamp; users see the staleness.
- A gold failure DEGRADES the UI to silver-direct queries (slower, less pretty). The UI shows a banner. Auto-recovery on next gold rebuild.
- An LLM call failure DEGRADES to a cheaper model, then to a structured "I cannot answer right now" response. Never auto-fabricate.

When a HALT or DEGRADE persists for > 60 minutes during market hours (AxiomFolio) or > 6 hours otherwise, the `infra-ops` persona auto-pages the founder.

## 6. What we will NOT do

- We will **not** delete bronze rows to "fix" a silver bug. Fix the silver transform; bronze is sacred.
- We will **not** use an LLM to "clean" bronze data without the cleaning being deterministic and reproducible.
- We will **not** ship a `force-delete-user-data` admin endpoint that bypasses the soft-delete + retention machinery.
- We will **not** let user A's data ever appear in user B's session, even on read-only views. Cross-tenant leak is a P0.
- We will **not** ingest bronze data from a source that doesn't have a stable `(source, source_id, fetched_at)` triple. We need to be able to re-fetch and prove provenance.

## Lineage & amendments

Authored 2026-04-23 as part of Docs Streamline 2026 Q2. Append-only.

### Amendments

_None yet._
