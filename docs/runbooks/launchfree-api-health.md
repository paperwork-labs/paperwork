---
owner: ops
last_reviewed: 2026-05-02
doc_kind: runbook
domain: launchfree
status: stub
---

# LaunchFree API health (`/health`)

> **Category**: ops
> **Owner**: @ops
> **Last verified**: 2026-05-02
> **Status**: active

**TL;DR:** Triage when Studio shows LaunchFree `/health` as failing (often 404). Check env, Render logs, and the real URL before you change probes.

<a id="launchfree-api-health"></a>

## Symptom

- Studio `/admin/infrastructure` shows **LaunchFree API** probe red with `GET /health → HTTP 404` (or legacy `HTTP 404`).
- Downstream: anything depending on LaunchFree API health checks may treat the product as unavailable.

## First look (founder / on-call)

1. Confirm the probed URL in Studio env: `LAUNCHFREE_API_URL` (default in code is the Render service base without path; probe appends `/health`).
2. In Render dashboard, open **launchfree-api** → **Logs** → filter for recent deploys and boot errors.
3. Hit the URL manually (curl or browser): `{LAUNCHFREE_API_URL}/health` — expect JSON health payload, not 404 HTML.
4. If the service moved behind a new path prefix (e.g. `/v1/health`), update **Studio** env `LAUNCHFREE_API_URL` or adjust the Brain/Studio probe target in `apps/studio/src/lib/command-center.ts` (separate PR — this runbook is triage only).

## Escalation

- If Render service is suspended or build-failed: restore service or roll back deploy via Render; track in incidents / Brain conversations.
- If routing/product decision: assign to LaunchFree owner; do **not** silence the Studio probe without fixing or intentionally downscoping the check (no green-washing a broken endpoint).
