---
title: Vercel quota audit (2026 Q2)
last_reviewed: 2026-04-28
owner: infra
status: read-only snapshot
audit_window_utc: "Rolling 30-day window ending 2026-04-28T03:44:47Z (script `generated_at_unix_ms`)"
---

# Vercel quota audit (2026 Q2)

Read-only audit of **Paperwork Labs** (`team_RwfzJ9ySyLuVcoWdKJfXC7h5`) deployment volume, build minutes, and deployment *source* attribution. Companion to the parallel **Render** and **GitHub Actions** quota audits (`docs/infra/RENDER_QUOTA_AUDIT_2026Q2.md`, `docs/infra/GITHUB_ACTIONS_QUOTA_AUDIT_2026Q2.md`). **No** Vercel project settings or workflows were changed.

**How numbers were produced:** `VERCEL_API_TOKEN` from `bash scripts/vault-get.sh VERCEL_API_TOKEN`, `TEAM_ID=$(jq -r '.teamId' scripts/vercel-projects.json)`. Python 3 iterated `GET https://api.vercel.com/v9/projects` and, per project, paginated `GET https://api.vercel.com/v6/deployments?projectId=…&teamId=…&limit=100[&until=…]` until the oldest row in a page was older than the rolling **30-day** cutoff (`now_ms − 30 × 86_400_000`). Build minutes used Vercel timestamps: `(ready − buildingAt) / 60_000` when both present.

**Commands (representative):**

```bash
VERCEL_TOKEN=$(bash scripts/vault-get.sh VERCEL_API_TOKEN)
TEAM_ID=$(jq -r '.teamId' scripts/vercel-projects.json)

curl -sfS -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v4/teams/$TEAM_ID"

curl -sfS -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects?teamId=$TEAM_ID&limit=100"

curl -sfS -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v6/deployments?projectId=prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT&teamId=$TEAM_ID&limit=100"

# Documented billing/usage endpoints (both failed in this audit — see §4):
curl -sS -w "\nHTTP:%{http_code}\n" -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v1/teams/$TEAM_ID/usage"
```

**Team plan (API):** `GET /v4/teams/{teamId}` reports `billing.plan`: **`hobby`**, consistent with quotas discussed below.

---

## 1. What we have — Vercel project inventory

**Team project list (`GET /v9/projects?teamId=&limit=100`):** exactly **six** linked projects returned. **`design`** — no **`prj_…`** appears on this team yet (canonical JSON still lists `TBD_CREATE_BEFORE_MERGE`). **`axiomfolio-next`** (`scripts/vercel-projects.json` → `prj_z3JVQGLLfsJO2QZJnK5BvMjfFoK3`): `GET https://api.vercel.com/v9/projects/prj_z3JVQGLLfsJO2QZJnK5BvMjfFoK3?teamId=…` returned **HTTP 404** — project absent or deleted; current production workload for Axiom on Vercel is **`axiomfolio`**.

Auto-promote is described in **`docs/infra/VERCEL_AUTO_PROMOTE.md`** and **`vercel-promote-on-merge`** (alias-only promote; **no** new build).

| Canonical app | Vercel name | Project ID | Framework | Repo / root (`v9/projects`) | `git.deploymentEnabled.main` (`apps/<app>/vercel.json`) | Git link (`productionBranch` from API) | Last 7d deploys | Last 30d deploys |
|---------------|-------------|------------|-----------|------------------------------|------------------------------------------------------------|----------------------------------------|-----------------|-------------------|
| studio | studio | `prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT` | nextjs | `paperwork-labs/paperwork`, `apps/studio` | true | `main` | 104 | 158 |
| distill | distill | `prj_1TKlkMmY3vLVNfAfRxUY57z43m11` | nextjs | `paperwork-labs/paperwork`, `apps/distill` | true | `main` | 101 | 155 |
| launchfree | launchfree | `prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7` | nextjs | `paperwork-labs/paperwork`, `apps/launchfree` | true | `main` | 102 | 156 |
| filefree | filefree | `prj_DNPGX5GrYcwer9oANv90NKqIT67I` | nextjs | `paperwork-labs/paperwork`, `apps/filefree` | true | `main` | 111 | 165 |
| axiomfolio (canonical Next shell in repo today) | axiomfolio | `prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE` | nextjs | `paperwork-labs/paperwork`, `apps/axiomfolio` | true | `main` | 19 | 19 |
| trinkets | trinkets | `prj_MFUxaJCbQuSdJZWWVgaEtRllKjzB` | nextjs | **`link.repo`** null; **`rootDirectory`** null — not Git-linked in API | true (intent in repo) | null | **0** | **0** |
| axiomfolio-next | — | *(not on team)* | — | *(GET by ID → 404)* | see `apps/axiomfolio/vercel.json` | — | — | — |
| design | *(no team project)* | TBD (`scripts/vercel-projects.json`) | — | `apps/design/vercel.json` exists locally | main enabled in file | — | — | — |

**Source mix (per project, rolling window):** each deployment row includes optional `source` (`git`, `cli`, `import`, `redeploy`, or **null**). Counts below are from the same pagination pass as the totals.

| Project | Last 7d `source` | Last 30d `source` | Avg build (min) when `buildingAt`+`ready` present — 7d / 30d | Total build minutes sum — 7d / 30d |
|---------|------------------|-------------------|-------------------------------------------------------------|------------------------------------|
| studio | git 99, cli 4, null 1 | git 153, cli 4, null 1 | 0.748 / 0.745 | 70.29 / 71.48 |
| distill | git 100, null 1 | git 154, null 1 | 0.362 / 0.363 | 30.40 / 31.23 |
| launchfree | git 102 | git 156 | 0.621 / 0.622 | 57.78 / 59.11 |
| filefree | git 111 | git 165 | 0.730 / 0.742 | 70.78 / 73.43 |
| axiomfolio | git 19 | git 19 | 2.788 / 2.788 | 52.97 / 52.97 |
| trinkets | — | — | — | — |

**Auto-promote / Git:** Repo `vercel.json` files reviewed: **`git.deploymentEnabled`** has **`main`: true** for `studio`, `distill`, `filefree`, `launchfree`, `axiomfolio`, `design`, `trinkets`. **`productionBranch`** in Vercel’s **Git Integration** (`link.productionBranch` on linked projects, `GET /v9/projects`): **`main`** for all five apps that have a Git link. **Dashboard-only settings** (e.g. “Ignored Build Step,” draft-PR previews) are **not** exposed on these list endpoints; do not assume they are disabled without dashboard confirmation.

---

## 2. Where the deploys come from (last 30d)

**Team-wide deployment count (sum of per-project `last_30d.total_deploys`, `trinkets` = 0):** **653** deployments with `createdAt` after the rolling cutoff.

**By `source` (sum across projects):**

| source | Count | Share |
|--------|------:|------:|
| `git` | 647 | **99.08%** |
| `cli` | 4 | 0.61% |
| `null` / unset | 2 | 0.31% |
| `import`, `redeploy` | 0 in this window (negligible in wider pagination for this team) | — |

**Important nuance — “API” vs list `source`:** Vercel’s Hobby **100/day** cap applies to **deployments created via the Deployments API** (see platform docs / incident narrative in `VERCEL_AUTO_PROMOTE` and PR **#321**). The **`/v6/deployments` list does not expose a dedicated `source: "api"` string** in this dataset; **no** deployment in the last-30d aggregate was labeled `source: "api"`. **Null** `source` with normal Git commit metadata may still be Git-integrated (see below). **Do not** equate `source: "git"` with “free” and everything else with “API quota” without billing-side confirmation.

**Last 7d (437 deploys summed):** **431** `git` (98.6%), **4** `cli`, **2** `null` — same story: almost entirely Git.

**Deployments with `source` null (possible mis-tag or non-standard path) — both on the same commit and same minute window as post–PR-321 recovery work:**

| When (UTC) | Project | Deployment | Target | `meta.githubCommitSha` | Notes |
|------------|---------|------------|--------|--------------------------|--------|
| 2026-04-28 (ms `1777340883374` / `1777340904646`) | studio, distill | `dpl_65pvNifxPBbzmpnHUStyfMUXHrDW`, `dpl_HwGAReJB9X4TaLQbzgWF5MEQ8n2o` | production | `386cd994f0b26a32e4a215b7a0f67a4c0af9baed` | Same SHA on two apps; **inspector:** `vercel.com/paperwork-labs/{studio|distill}/…`. **Not** labeled `git` in list response; treat as **audit / recovery-related** until confirmed in dashboard. |

**CLI deploys (all `studio`, last 30d):** four production deploys, **local `vercel` / Cursor CLI** pattern (`meta.actor`: `cursor-cli` on two rows):

| When (UTC) | UID | Target | Ref / SHA / actor |
|------------|-----|--------|-------------------|
| 2026-04-27T08:18:54Z | `dpl_4zQdH6JcgAa6qqwRfT7QSGWR6SzV` | production | ref `chore/clerk-key-propagation-report`, **cursor-cli** |
| 2026-04-25T16:13:52Z | `dpl_DX1Hd2edPtWVR82uJu1ZWDVwMv6c` | production | ref `main`, **cursor-cli** |
| 2026-04-25T10:08:58Z | `dpl_7UydhoLLrUhTNepLFofM7RnhrxEc` | production | SHA `d5198aa…` |
| 2026-04-25T07:41:26Z | `dpl_F9uSRfbxr1xaRaDgs6VD518BShmN` | production | SHA `d5198aa…` |

These are **not** auto-promote (promote does not create a deployment row as a new build). They are **discretionary CLI production builds** — align with **PR #321** “no recovery reflex via `POST /v13/deployments`” except when explicitly approved.

---

## 3. Burn rate

**Calendar pattern:** In the rolling 30-day window, **Distill** (and the team overall) show deploys clustered on **seven UTC dates** (`2026-03-29`, `03-30`, `04-24` … `04-28`), with **no** recorded deployments between **UTC 2026-03-31 and 2026-04-23** on projects that paginate with real activity (validated by paging Distill deployments and filtering `createdAt ≥ cutoff`). Interpret as **bursty merges** vs continuous daily churn.

**Daily totals (UTC, all six projects summed by `strftime("%Y-%m-%d")` on `createdAt`):**

| Date (UTC) | Deploys | `git` | `cli` | `null` flagged as non-git bucket* | Approx. summed build minutes** |
|------------|--------:|------:|------:|-----------------------------------|-------------------------------|
| 2026-04-15 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-16 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-17 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-18 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-19 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-20 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-21 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-22 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-23 | 0 | 0 | 0 | 0 | 0 |
| 2026-04-24 | 139 | 139 | 0 | 0 | 66.46 |
| 2026-04-25 | 95 | 92 | 3 | 0 | 45.85 |
| 2026-04-26 | 101 | 101 | 0 | 0 | 36.63 |
| 2026-04-27 | 90 | 89 | 1 | 0 | **103.43** (highest build-minute day) |
| 2026-04-28† | 12 | 10 | 0 | 2 | 29.87 |

\*Table `apiish` column in the internal tally treated **`null` source** as “non-git **for labeling only**”; **this is not** Vercel’s billing “API deployment” counter.
\*\* Sum of `(ready − buildingAt)` where both set; understated when timestamps missing.

†Partial day (audit run ~`2026-04-28T03:44Z` UTC).

**Worst UTC day — deployment count:** **2026-04-24** with **139** team deployments (all **`git`** in tally).

**Worst UTC day — build minutes:** **2026-04-27** with **~103.4** summed minutes (heavy concurrent app builds).

**30d averages:**

- **Rough non-`git` deployment rows:** `(4 cli + 2 null) / 30` ≈ **0.20/day** — **not** the same as Vercel’s internal “API deployments/day” billing counter.
- **Team build minutes (sum of per-project `total_build_minutes_sum`):** \(52.97 + 31.23 + 71.48 + 59.11 + 73.43\) ≈ **288.2** minutes in \~29–30 effective days → **~9.6 min/day** average (dominated by burst days).

**Project most likely to hit build-time pressure (30d sum of build minutes):** **filefree** (~73.4 min), then **studio** (~71.5 min), then **axiomfolio** (~53.0 min, fewer deploys but **longer** average build ~2.8 min).

---

## 4. How close are we to the caps?

Assumptions: **Hobby** per `GET /v4/teams/{teamId}`; public docs cite **~6,000 build minutes/month** and **100 GB bandwidth** and **API deployment** daily limits — **exact enforcement is billing-side**.

| Cap (Hobby, order-of-magnitude) | What we measured | Headroom / signal |
|---------------------------------|------------------|-------------------|
| **~100 “API” deployments/day** | List API shows **0** rows with `source: "api"`; **4** `cli` + **2** `null` in 30d (~0.2/day non-`git` rows) | **Large** headroom on this **proxy**; **cannot** assert actual billable “API deployment” count without dashboard/billing. |
| **~6,000 build minutes/month** | **~288** minutes summed build time (timestamp-based) in rolling 30d | **~\~4.8%** of 6,000 if month ≈ window; **no** 70% trend. |
| **~100 GB bandwidth/month** | `GET /v1/teams/{teamId}/usage` → **HTTP 404** | **Vercel API does not expose this** to this token in this audit. |

**Near-miss (70% rule):** **No** cap in the table above approaches 70% on observed metrics. **Recommendation:** Still add **Brain** metering (§6) — **billing UI** is authoritative for spikes the REST list misses.

---

## 5. Concrete recommendations (by leverage)

| # | Recommendation | Evidence | Estimated savings | Risk |
|---|----------------|----------|---------------------|------|
| a | **Prefer Git-driven builds; avoid CLI production deploys** unless runbook‑approved (`vercel deploy --prod`). | Four **CLI** prod deploys on **studio** (Cursor CLI actors on 2). | Fewer discretionary builds (**minutes**); avoids accidental Hobby friction. | Low if paired with documented promote path (`vercel-promote-on-merge`). |
| b | **`productionBranch: main` + Dependabot-only `ignoreCommand` already documented** (`apps/*/vercel.json`). Extend **doc‑only merges** sparingly — merges still enqueue many **Git** previews per app. | `ignoreCommand` only skips Dependabot, not arbitrary docs. | **Zero** doc-only savings today without stronger **path filters** / ignore rules. | High if `ignoreCommand` widened without testing every app. |
| c | **Preview cancellation:** Vercel typically cancels stale preview builds on new pushes; **production** behavior is product-default — **not verified** per-app in this read-only audit. | — | Unknown (likely small vs preview churn). | Misconfiguration could skip needed prod builds. |
| d | **Eliminate API-style recovery deploys** except founder‑blessed runbooks (**PR #321**). Incident text in **`latestDeployments.meta`** explicitly references **`POST /v13/deployments`** class mistakes. | **2** mis-tagged **`null`** + **CLI** pattern; no sustained **`api`** label. | Prevents repeating **quota / 402** class incidents. | **Promote-alone** fixes need a **READY** Git SHA — still operational work. |
| e | **`design`:** no **`prj_…`** on team — **nothing to throttle** yet. **`trinkets`:** Git not linked (**`link.repo`** null); **zero** deployments in window — reconcile matrix vs reality before investing Storybook infra. | `GET /v9/projects` & deployment pagination. | Avoids orphan project maintenance. | Naming / linking mistakes block real deploys. |

---

## 6. Brain integration plan — `vercel_quota_monitor`

**Goal:** Align with **GitHub Actions** + **Render** monitors: **`apis/brain/app/schedulers/quota_monitors/`** owns one scheduled job per vendor.

### Scheduler job

| Field | Value |
|-------|--------|
| Name | `vercel_quota_monitor` |
| Driver | **APScheduler** (same pattern as other Brain jobs) |
| Interval | **Every 4 hours** |
| Gate | Run only when **`BRAIN_SCHEDULER_ENABLED`** is truthy (same as other schedulers). |

**Read-only API steps (token from Secret / env, team from config):**

1. `GET /v9/projects?teamId={teamId}&limit=100` — enumerate `projectId`, `name`.
2. For each project: `GET /v6/deployments?projectId=&teamId=&limit=100` with `until` pagination — collect rows with `createdAt ≥ now − 24h`.
3. Optionally `GET /v4/teams/{teamId}` for plan changes / entitlements cache.
4. **If** a future usage endpoint is enabled: call it; else store `usage_error` in `extra_json`.

### `VercelQuotaSnapshot` model (design only — **do not implement** in this PR)

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID / bigserial | PK |
| `recorded_at` | timestamptz | Job completion time |
| `team_id` | text | e.g. `team_RwfzJ9ySyLuVcoWdKJfXC7h5` |
| `project_id` | text | `prj_…` |
| `project_name` | text | Slug |
| `api_deploys_24h` | int | **Define** as rows where `source in ('api', …)` **or** billing export when available; until then **nullable** with `extra_json` carrying raw `source` histogram |
| `git_deploys_24h` | int | `source == "git"` |
| `cli_deploys_24h` | int | `source == "cli"` |
| `total_deploys_24h` | int | All rows in window |
| `build_minutes_24h` | float | Sum of `(ready-buildingAt)` when defined |
| `bandwidth_gb_24h` | float nullable | Populate when Usage API exists |
| `extra_json` | jsonb | Raw histogram, HTTP errors (`usage 404`), pagination depth |

### Alarms (GitHub Issues)

Tag: **`infra-alert`**, **`vercel-quota`** (shared prefix pattern with **`render-quota`**, **`gh_actions-quota`**).

| Condition | Action |
|-----------|--------|
| If **estimated** billable API deploy count (once defined) summed across projects **> 70** in trailing 24h **or** `source=api` histogram proxy exceeds policy | **Open** P2 issue immediately with snapshot JSON |
| If **trailing 7‑day rolling average** of daily non-`git` deploys (\(cli + null\) or billing metric) **> 50**/day | **Open** “trend investigation” issue |
| Build minutes: **month‑to‑date** vs **elapsed‑month pacing** exceeds **+10 percentage points** | Open trend issue |

### Studio surface

| Piece | Responsibility |
|-------|----------------|
| Brain | `GET /api/v1/admin/vercel-quota` → last **30** daily rollup rows **+** latest 24h breakdown |
| Studio | **`/admin/infrastructure`** — shared **`quota-panel.tsx`** (below) renders **Vercel + Render + GitHub Actions** side‑by‑side |

---

## 7. Convergence with the other two audits

All three audits should land **matching shapes**:

| Concern | Pattern |
|---------|---------|
| Brain code layout | **`apis/brain/app/schedulers/quota_monitors/{vercel,render,gh_actions}.py`** |
| Persistence | **`VercelQuotaSnapshot`**, **`RenderQuotaSnapshot`**, **`GitHubActionsQuotaSnapshot`** (parallel tables, same retention policy class) |
| Admin API | **`GET /api/v1/admin/{vercel,render,gh_actions}-quota`** |
| Studio UI | One shared **`apps/studio/src/app/admin/infrastructure/quota-panel.tsx`** composes all three |
| Issue labels | **`infra-alert,<platform>-quota`** (e.g. `vercel-quota`, `render-quota`, `gh-actions-quota`) |

**Architecture (one paragraph):** Three lightweight schedulers run on **Brain** behind **`BRAIN_SCHEDULER_ENABLED`**, each performing **read-only** vendor API polls and **upserting** append-only **`{Vendor}QuotaSnapshot`** rows (**Postgres**). **Studio’s** infra page calls **thin JSON endpoints** (`/api/v1/admin/{platform}-quota`) and **`quota-panel.tsx`** merges the series so operators see **Vercel, Render, and GitHub Actions** quota telemetry with **parallel alarm routing** via **GitHub Issues** + **`infra-alert`**.

---

## Executive snapshot (parent handoff)

- **Branch / PR:** `chore/vercel-quota-audit` — open PR titled **`docs(infra): Vercel quota deep-dive + Brain monitor plan`** (create with `gh pr create` after push).
- **Top finding:** **`source: "git"` ≈99%** of deployments in the 30‑day rolled window (**647/653**). **Four** discretionary **`cli`** production deploys (all studio) and **two** **`source: null`** production deploys (studio+distill, same SHA) deserve **manual** dashboard confirmation — **not** a sustained “API deployment storm.”
- **Top 3 recommendations:** (1) **Keep PR #321 discipline** — avoid **`POST /v13/deployments`** recovery; rely on Git SHA + **`vercel-promote`**; (2) **Stop ad-hoc CLI prod** on studio/Cursor paths unless blessed; (3) **Wire Brain `vercel_quota_monitor`** + **`infra-alert`** so **billing-adjacent** spikes are caught early.
- **Unified monitor architecture:** See **§7** — **one panel**, **three snapshot tables**, **three schedulers**, **shared label scheme**.

---

*Read-only audit. Numbers from Vercel REST list endpoints; usage/bandwidth not available via tested routes.*
