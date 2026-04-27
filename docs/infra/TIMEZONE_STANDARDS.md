---
owner: infra-ops
last_reviewed: 2026-04-26
doc_kind: runbook
domain: infra
status: active
---

# Timezone standards (Paperwork Labs)

## Canonical rule

All datetimes stored in the database, transmitted in API responses, logged for audit, scheduled at the **system** level, and compared in server-side business logic are **UTC and timezone-aware**. The browser or client converts to the **user’s local timezone only at the render boundary** (formatting for display), never earlier in the pipeline. Founder direction: **“UTC in DB everywhere, user’s timezone when client-facing / UI.”**

## Why this matters

AxiomFolio already follows this pattern in most hot paths: models use `DateTime(timezone=True)`, serializers favor ISO 8601, and `datetime.now(timezone.utc)` appears throughout services and tasks. Storing and exchanging **UTC** matches ISO 8601 practice, keeps APIs unambiguous (suffix `Z` or explicit offset), and avoids daylight-saving gaps and duplicates when interpreting “wall clock” times. For **audit and forensics**, a single canonical instant in UTC is comparable across regions and matches how Postgres `timestamptz` behaves when clients send or receive aware timestamps.

## Implementation rules by surface

### Python (FastAPI services)

- Prefer **`datetime.now(timezone.utc)`** for “now” in UTC.
- Do **not** use **`datetime.utcnow()`** (deprecated in Python 3.12+, always naive).
- Do **not** use bare **`datetime.now()`** when the value is persisted, returned in JSON, or compared to aware datetimes from the DB — use UTC awareness.
- **Pydantic v2:** use `Field(default_factory=lambda: datetime.now(timezone.utc))` where defaults need “now”.
- **SQLAlchemy:** use `DateTime(timezone=True)` for all instants; align legacy `DateTime` columns with a **planned migration** (not ad-hoc in feature PRs).

### APScheduler (Brain)

- Every **`CronTrigger`** and **`IntervalTrigger`** MUST pass **`timezone=...` explicitly** (see APScheduler docs). Default for system jobs: **`timezone.utc`** (or the string `"UTC"` where the API requires it).
- **Exceptions:** Jobs that intentionally mirror **n8n workflows whose schedule is meaningful in Pacific wall time** (migrated from `America/Los_Angeles` in the export) MUST use **`ZoneInfo("America/Los_Angeles")`** on the trigger and a **code comment** explaining why. Do **not** silently shift wall-clock cadence when cutting over from n8n.
- **Approved LA exceptions** (revisit after T2.4 cutover):

| Job / workflow area | Trigger timezone | Rationale |
| ------------------- | ---------------- | --------- |
| Data Source Monitor (n8n P2.8) | `America/Los_Angeles` (when Brain-owned) | n8n export uses LA `settings.timezone`; weekly wall time must match ops intent until product re-baselines to UTC. |
| Data Deep Validator (P2.9) | `America/Los_Angeles` | Same. |
| Annual Data Update (P2.10) | `America/Los_Angeles` | Same. |
| Credential Expiry (n8n) | `America/Los_Angeles` | Export uses LA; Brain cutover must preserve wall time or document UTC rebaseline. |
| Sprint Close / Kickoff (n8n) | TBD with product | Wall-clock meaning (e.g. “Friday 9pm PT”) must be explicit on cutover. |

*Shadow mirrors today register the same cron **expression** in **UTC**; wall-clock parity with LA-tagged n8n is **not** guaranteed — see [BRAIN_SCHEDULER.md](./BRAIN_SCHEDULER.md).*

### Next.js / Vite (frontend)

- API routes and server code should emit **ISO 8601 with `Z`** (or explicit offset) for instants.
- **Server Components** should pass **ISO strings** to **Client Components**, not live `Date` objects, to avoid hydration skew.
- Client formatting example:

```tsx
const userTimeZone =
  typeof window !== "undefined"
    ? Intl.DateTimeFormat().resolvedOptions().timeZone
    : "UTC";

export function useUserTimeZone(): string {
  return userTimeZone;
}

export function formatDateTime(iso: string, timeZone: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(d);
}
```

*(Full frontend migration — explicit `timeZone` on every `toLocale*` call and saved user preference — is a separate sprint; this PR documents the target only.)*

### Database

- Prefer **`timestamp with time zone`** (`DateTime(timezone=True)`) for all instants.
- Server defaults: use **`func.now()`** in UTC-aware columns on Postgres, or **`func.timezone('UTC', func.now())`** where the dialect requires it — avoid naive `datetime.utcnow` in Python defaults for aware columns.

### Logging

- Structured logs should emit **ISO-8601 UTC** (with `Z` or offset). Avoid relying on the host’s local timezone for log lines in shared aggregators.

### Slack

- Avoid hard-coding **“PT” / “PST”** in copy that is read globally. Prefer Slack’s **`<!date^unix^{date_short_pretty} {time}|fallback>`** for user-local rendering, or omit wall time if it is not actionable.

### n8n compatibility

- When porting a job that was **LA-scheduled** in n8n and the schedule is **meaningful in PT** (e.g. sprint-close at a specific PT time), document it in this file’s exception table and register the Brain trigger with **`ZoneInfo("America/Los_Angeles")`**. Do not silently change cadence.

## Test discipline

Any code that calls `datetime.now(...)` should be testable with a **fake clock** (thin wrapper module, e.g. `app/utils/clock.py` with `utc_now()`), so tests can freeze time without monkeypatching the stdlib globally.

## Lint enforcement

| Package | Ruff | Notes |
| ------- | ---- | ----- |
| `apis/brain` | `extend-select = ["DTZ"]` | **Blocking in CI** (`ruff check .` in Brain workflow). |
| `apis/axiomfolio` | `extend-select = ["DTZ003"]` | Bans **`utcnow`** immediately; expand to full **DTZ** after the broad `datetime.now()` sweep (~182 findings as of 2026-04-26). |

Optional **pre-commit** (repo-wide): add a hook running `ruff check --select DTZ` on `apis/*`.

## Follow-up / founder–product decisions

Detailed tables live in **`/tmp/tz-audit/inventory.md`** (recon output). Track internally:

1. **Alembic migrations** for any remaining `DateTime` without `timezone=True` / `timestamp without time zone`.
2. **Frontend:** `toLocaleDateString` / `toLocaleTimeString` without explicit `timeZone`; Studio admin hardcoded `America/Los_Angeles`.
3. **Slack:** strategy for `<!date^...>` vs UTC-only operational messages.
4. **Render / Hetzner:** set service-level **`TZ=UTC`** where not already set (Dockerfiles now set `ENV TZ=UTC` for API images).
5. **Overlap with cron cutover branches** (e.g. PRs **#227 / #233 / #235**): do not re-edit the same scheduler files without coordinating — this PR avoids `n8n_mirror.py`, `sprint_auto_logger.py`, and `infra_health.py` trigger tweaks.

## Related docs

- [BRAIN_SCHEDULER.md](./BRAIN_SCHEDULER.md) — SQLAlchemy job store, n8n shadow mirrors, **LA caveat**.
- [RENDER_INVENTORY.md](./RENDER_INVENTORY.md) — deployment surface (pair with ops for `TZ` on Render).
