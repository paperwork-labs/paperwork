---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: infra
status: active
severity_default: red
---
# Runbook: Deploy Pipeline Failure

> **Owner:** On-call ops. The **Deploy Health** admin tile or **Pre-merge Deploy Gate** is failing; this runbook classifies the cause and restores green deploys. **Severity:** YELLOW = advise; RED = halt merges and investigate. **Related:** G28 (deploy-health guardrail), D120, R34/R38 (silent-fallback class).

## When this fires

The admin dashboard tile **Deploy Health** flips YELLOW or RED, or the
`Pre-merge Deploy Gate` CI check fails on a PR.

- Red tile with reason `N consecutive failed deploys (threshold 3)` on one
  or more Render services
- The background Beat job `app.tasks.deploys.poll_deploy_health` has
  written ≥1 `is_poll_error=True` row recently (Render API unreachable)
- A PR check `Pre-merge Deploy Gate` fails with `HTTP 200` and
  `status=red` from `/api/v1/admin/deploys/health`

## Triage

**Do not panic or revert blindly.** The midnight-merge-storm incident
(2026-04-20, see `docs/handoffs/2026-04-20-midnight-merge-storm.md`) was a
Render infra event, not a code regression. Before reverting any PR:

1. Does the build log show a stack trace, lint failure, or test failure?
   → Code. Go to `## Path: Code regression`.
2. Does the build log show `billing`, `quota`, `pipeline disabled`, or an
   infra-side error before the container started? → Render. Go to
   `## Path: Render/infra`.
3. Did the build never start (`created` → `build_failed` in seconds with
   no logs)? → Almost always billing/quota. Go to `## Path: Render/infra`.

**Classify (≤5 min):**

```bash
# Which services are red?
curl -sS -H "Authorization: Bearer $PROD_HEALTH_TOKEN" \
  https://api.axiomfolio.com/api/v1/admin/deploys/health | jq '.services[] | select(.status=="red")'

# Last 10 events across all monitored services
curl -sS -H "Authorization: Bearer $PROD_HEALTH_TOKEN" \
  https://api.axiomfolio.com/api/v1/admin/deploys/health | jq '.events[0:10]'
```

Record in the incident log: service(s), status, commit SHAs, first
failure timestamp.

## Path: Code regression

1. `gh pr list --state merged --base main -L 10` — last 10 merged PRs.
2. Identify the last GREEN deploy's commit SHA from the `events` array.
   All PRs merged after that SHA are suspects.
3. If you can correlate the failing SHA to a single PR, `gh pr view <N>`
   and read the diff.
4. If the failure is deterministic (stack trace, missing migration, env
   var), either:
   - Fix forward with a new PR if the fix is <30 min.
   - `git revert <sha>` if triage will exceed 30 min. Open the revert PR;
     the `Pre-merge Deploy Gate` will still run.
5. **Never** force-merge past the deploy gate. If the gate is wrong, fix
   the check; do not bypass it.

## Path: Render/infra

Typical causes:

- Billing / quota on the Render workspace
- Build pipeline disabled (Render side)
- Docker registry or apt mirror outage mid-build

Actions:

1. Log into Render dashboard → `axiomfolio-api` → Deploys. Open the first
   failed deploy and read logs.
2. Check workspace billing at `Settings → Billing`.
3. If billing is clear but builds still fail, open the Render status page
   and a support ticket quoting the failing deploy id.
4. While infra is degraded, follow `## Escalation`.
5. Once a fresh deploy reaches `live`, the composite tile auto-recovers
   on the next 5-minute Beat cycle. Run **Poll now** on the admin tile to
   force a refresh, then `## Verification`.

## Path: Poll-error (telemetry outage)

If the tile shows YELLOW with reason containing `poll error`:

- Check `RENDER_API_KEY` is present in the API service env.
- Check Render API status: `https://api.render.com/v1/services`.
- Last `poll_error_message` in the events list usually names the cause
  (401, 429, timeout). Fix the underlying issue; the next 5-min Beat
  cycle clears the YELLOW.

## Verification

After a fix or a successful deploy to `live`:

- Call the API liveness probe (expect `200` and JSON with healthy status):

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://api.axiomfolio.com/health
```

- Confirm deploy health is no longer red for affected services (same
  tokened endpoint as triage); composite tile should return to green on
  the next Beat cycle (5 min) or immediately after **Poll now**.

```bash
curl -sS -H "Authorization: Bearer $PROD_HEALTH_TOKEN" \
  https://api.axiomfolio.com/api/v1/admin/deploys/health | jq '.services'
```

- No new `is_poll_error=True` rows for the current incident window (use
  appendix SQL if needed).

## Rollback

- If you took `## Path: Code regression` and a fix-forward or revert did
  not work: `git revert <sha>` and ship the revert PR; the
  `Pre-merge Deploy Gate` still applies.
- If a deploy made things worse: restore the previous good deploy via
  Render dashboard → Service → **Deploys** → select previous → **Redeploy**.

## Escalation

- **Primary:** `#ops` on Slack — post: deploys RED, N consecutive
  failures, root cause = ___, holding merges to main. The
  `Pre-merge Deploy Gate` keeps the queue held; do **not** bypass.
- **When to pull a human:** unclear root cause after triage, billing or
  vendor action required, or any RED tenant-facing impact. DM or @ the
  infra on-call in `#ops` per the current on-call rota.
- **Vendor:** open a Render support ticket with deploy id; link the
  ticket in `#ops`.

## Post-incident

If you reverted a PR or found a code issue, log:

- New `R##` entry in `docs/KNOWLEDGE.md` for the failure pattern
- If a new guardrail emerged, `.cursor/rules/*.mdc` update

If it was infra-only, drop a short note in the handoff file of the day
(`docs/handoffs/YYYY-MM-DD-*.md`) so the next agent knows the code is
clean.

If the runbook was wrong or stale, update it before closing the ticket
and bump `last_reviewed`.

## Appendix

### Manual poll

```bash
# Trigger an immediate poll (admin-auth required)
curl -sS -X POST -H "Authorization: Bearer $PROD_HEALTH_TOKEN" \
  https://api.axiomfolio.com/api/v1/admin/deploys/poll | jq
```

### SQL quick views

```sql
-- Worst offenders last 24h
SELECT service_slug, status, count(*) AS n
FROM deploy_health_events
WHERE render_created_at > now() - interval '24 hours'
GROUP BY 1,2
ORDER BY 3 DESC;

-- Consecutive-failure streak per service
WITH ranked AS (
  SELECT service_slug, deploy_id, status, render_created_at,
         row_number() OVER (PARTITION BY service_slug ORDER BY render_created_at DESC) AS rn
  FROM deploy_health_events
  WHERE NOT is_poll_error AND status IN ('live','build_failed','update_failed','canceled')
)
SELECT service_slug, count(*) AS streak
FROM ranked
WHERE rn <= 20 AND status <> 'live'
GROUP BY 1
ORDER BY 2 DESC;
```
