---
owner: infra-ops
last_reviewed: 2026-04-28
doc_kind: audit
domain: infra
status: draft
---

# Render pipeline minutes — quota audit (2026 Q2)

**Context:** Workspace billing shows **~1,078 / 500** included pipeline minutes month-to-date (~115% overage, ~\$2.89 unbilled at published overage rates — figures from founder; not re-derived here).

**Methodology (API, read-only):**

- Queried `GET https://api.render.com/v1/services?limit=100` with a Render API token (vault: `RENDER_API_KEY`).
- For each service `sid`, paginated `GET /v1/services/{sid}/deploys?limit=100` until the oldest deploy in a page started **before** a rolling **30-day** cutoff (`now_utc − 30d` at audit run time: **2026-04-28T03:42Z** → cutoff **2026-03-29T03:42Z**).
- **Approximate pipeline minutes per deploy:**  
  \(\text{minutes} = (\text{finishedAt} − \text{startedAt})\) in minutes, **only when both timestamps exist** and `finishedAt ≥ startedAt`.
- **Important:** This is **not** identical to Render’s billing dashboard month boundary (calendar month-to-date). Numbers below are **rolling 30 days** from the audit timestamp. Totals also omit anything outside deploy-history pagination limits (none hit here).

**Workspace:** owner id `tea-d6uflspj16oc73ft6gj0` (Paperwork team, per inventory).

**Usage API:** Probed `GET /v1/owners/tea-d6uflspj16oc73ft6gj0/usage`, `/metrics`, and shallow variants — all returned **404** (`page not found`). There is **no** validated public REST path here for invoice-grade pipeline totals; Brain must either use documented billing endpoints when available or **derive** usage from deploy durations (below).

---

## 1. What we have

| Service | Type | Plan | Build runtime | Root dir | Repo | Auto-deploy | Last ~30d: build attempts¹ | Successful (`live`) | Approx. avg build duration² | Approx. total pipeline min³ |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: |
| **filefree-api** | Web | Starter | Native Python (`runtime: python`) | _(empty)_ | `paperwork-labs/paperwork` | yes (`commit`) | 182 | 1 | ~132 s | **~399** |
| **brain-api** | Web | Starter | Docker (`runtime: docker`), `dockerfilePath` `apis/brain/Dockerfile`, `dockerContext` `.` | _(empty)_ | `paperwork-labs/paperwork` | yes (`commit`) | 190 | 1 | ~101 s | **~319** |
| **axiomfolio-api** | Web | Standard | Docker | `apis/axiomfolio` | **`paperwork-labs/axiomfolio`** ⚠️ | yes | 2 | 1 | ~131 s | ~4 |
| **axiomfolio-worker** | Worker | Standard | Docker | `apis/axiomfolio` | **`paperwork-labs/axiomfolio`** ⚠️ | yes | 2 | 1 | ~95 s | ~3 |
| **axiomfolio-worker-heavy** | Worker | Standard | Docker | `apis/axiomfolio` | **`paperwork-labs/axiomfolio`** ⚠️ | yes | 2 | 1 | ~92 s | ~3 |
| ~~**axiomfolio-frontend**~~ _(RETIRED **2026-04-30**)_ | Static site | _(API blank)_ | Static (`type: static_site`) | `apps/axiomfolio` | **`paperwork-labs/axiomfolio`** ⚠️ | yes | 4 | 1 | ~55 s | ~4 |

¹ **Build attempts:** deploy rows whose `startedAt` falls inside the rolling window (includes superseded/canceled/failed).

² **Average:** mean of `(finishedAt − startedAt)` over deploys with valid durations in that window.

³ **Sum** of those durations → approximate pipeline minutes attributed to that service in the window.

**Combined approximate rolling-30d pipeline minutes (sum of column): ~732 min.**  
(Historical snapshot: **`axiomfolio-frontend`** row above existed at audit time and was **retired from Render 2026-04-30**.)  
Dashboard **~1,078 MTD** is higher — consistent with **calendar month**, **different cutoff**, or additional billing mechanics not exposed on deploy objects alone.

### Deploy status breakdown (high signal)

**brain-api** (`srv-d74f3cmuk2gs73a4013g`) — approximate minutes by `status`:

| Status | Count | Approx. sum of build durations (min) |
| --- | ---: | ---: |
| `update_failed` | 135 | ~220 |
| `deactivated` | 51 | ~97 |
| `live` | 1 | ~2 |
| `canceled` | 2 | ~0.1 |
| `build_failed` | 1 | ~0.3 |

**filefree-api** (`srv-d70o3jvkijhs73a0ee7g`):

| Status | Count | Approx. sum (min) |
| --- | ---: | ---: |
| `deactivated` | 181 | ~397 |
| `live` | 1 | ~2 |

**Interpretation:** Render uses **`deactivated`** for deploys superseded when a newer deploy starts (push churn). Those rows **still carry `startedAt`/`finishedAt`**, so **wall-clock build time accrues** to pipeline minutes (same as failures — Render bills **build minutes executed**, including failed builds).

---

## 2. Where the minutes go

### Top 3 services by approximate rolling-30d pipeline minutes

1. **filefree-api — ~399 min** — dominated by **`deactivated`** deploy volume (~181 / 182 attempts).
2. **brain-api — ~319 min** — dominated by **`update_failed`** (~135 attempts ≈ ~220 min) plus **`deactivated`** (~97 min).
3. **axiomfolio-api — ~4 min** (tie with frontend/workers within rounding).

### Auto-deploy on every push including docs-only?

- Root [`render.yaml`](../../render.yaml) has **no `buildFilter`** (paths / ignoredPaths) on **`brain-api`** or **`filefree-api`** — both use repo root (`rootDir` empty). Per Render’s blueprint spec, **`rootDir`** scopes triggers for subtree services; **without `buildFilter`, changes anywhere in the monorepo can trigger auto-deploy** for root-level web services.
- **Conclusion:** Monorepo pushes to `main` **can** enqueue Docker/Python builds for Brain + FileFree regardless of whether the diff touched only `docs/` or `.github/` — unless dashboard-side filters were added outside `render.yaml` (not verified here).

### Build duration outliers

- **brain-api** vs **axiomfolio** Docker peers: similar band (~92–131 s average in window). No stable **5+ min** vs **2 min** split — builds are ~1.5–2.5 min wall time **when measured**.
- **Outlier pattern is frequency**, not slow single builds: hundreds of **`deactivated`** / **`update_failed`** cycles vs single-digit deploys on stale-repo AxiomFolio services.

### Failed builds vs minutes

- **Confirmed by observation:** **`update_failed`** rows include full **`startedAt`/`finishedAt` spans** (~220 min summed on brain-api alone). Industry-standard SaaS metering bills **compute time consumed**, not success.
- Operational takeaway: **fixing Brain’s repeated failures stops recurring minute burns immediately.**

---

## 3. Why we're overshooting

### (a) Brain failing repeatedly on `main` — commits `386cd99` / `78e6501` / `1cd3513`

**Validated.**

| Commit (short) | Deploy ID | Status | Started (UTC) | Finished (UTC) | Δ (~min) |
| --- | --- | --- | --- | --- | ---: |
| `386cd99` | `dep-d7o0o0ek1jcs739rmqq0` | `update_failed` | 2026-04-28T01:23:14Z | 2026-04-28T01:24:49Z | ~1.6 |
| `78e6501` | `dep-d7o0d5navr4c73flbia0` | `update_failed` | 2026-04-28T01:00:06Z | 2026-04-28T01:02:50Z | ~2.8 |
| `1cd3513` | `dep-d7o07a6gss3c73fckrjg` | `update_failed` | 2026-04-28T00:48:13Z | 2026-04-28T00:49:46Z | ~1.6 |

All three show **`trigger: new_commit`** in the deploy payload (same merge cadence as every other automatic deploy).

**Over the rolling window:** brain-api logged **135** `update_failed` deploys (~**220** approximate pipeline minutes attributed to that status alone). That supports **(a)** as a major contributor — not only three commits.

### (b) “AxiomFolio API + 2 workers + 1 frontend = 4 builds per push”

**Refuted for *live API wiring today*.**

Live services **`axiomfolio-api`**, **`axiomfolio-worker`**, **`axiomfolio-worker-heavy`** still point at **`https://github.com/paperwork-labs/axiomfolio`**, not the monorepo (Render API `repo` field). ~~**`axiomfolio-frontend`**~~ was **retired 2026-04-30** (UI on Vercel). In the rolling window each remaining service had **2–4** deploy attempts — **not** multiples of every monorepo push.

After **[RENDER_REPOINT](RENDER_REPOINT.md)** / blueprint sync repoints those services at **`paperwork-labs/paperwork`**, **(b) becomes a real risk**: parallel Docker builds per relevant merge unless **`buildFilter`** / **`rootDir`** discipline is applied (formerly four builds including static frontend; now three backends).

### (c) Auto-deploys trigger from `main` regardless of path changed

**Validated for monorepo-connected services.**

`render.yaml` documents auto-deploy on commit to `main` for blueprint-managed services; **`brain-api`** and **`filefree-api`** have **no `buildFilter`** and empty **`rootDir`**. **`axiomfolio-*`** entries use **`rootDir: apis/axiomfolio`** — once repointed to the monorepo, changes outside `apis/axiomfolio/` **should not** trigger those services (Render docs: root directory behavior).

---

## 4. Concrete recommendations

Ordered by **leverage** (cheap / high impact first).

| # | Change | Est. monthly minute savings | Risk | Implementation outline |
| --- | --- | --- | --- | --- |
| 1 | **Unblock Brain deploys:** diagnose **`update_failed`** root cause (image push, registry, Dockerfile, health check, migration, OOM — pull **Deploy** + **Logs** in Render for `dep-d7o0o0ek1jcs739rmqq0` lineage) and ship a green deploy. Every avoided failure cycle saves **~1.5–3 min × N merges**. | **Tens to 200+ min** while failure mode persists (scales with merge rate) | Low — restores production deploy path | Operational: fix failure; merge; verify `live` |
| 2 | Add **`buildFilter`** to **`brain-api`** (and optionally **`filefree-api`**) so only paths relevant to each service trigger builds — e.g. `paths` glob for `apis/brain/**`, `.cursor/rules/**`, shared packages if any. | **High** if many merges skip those paths (docs-only, other apps) — **50–300+ min**/month in active monorepo dev (rough; measure after 2 weeks) | Medium — a change that skips a needed deploy if filters are too tight; mitigate with explicit includes for shared libs | Edit root `render.yaml` per [Render `buildFilter`](https://render.com/docs/blueprint-spec); **Sync Blueprint**; verify one doc-only push does **not** queue build |
| 3 | Enable **“auto-deploy after CI checks pass”** (Render dashboard / supported API) where appropriate so GitHub **`ci.yaml`** gates deploy. | Saves minutes on **broken** commits that would fail fast in CI | Medium — slower time-to-prod; requires reliable CI | Dashboard: Deploys → settings; align with GitHub branch protection |
| 4 | ~~**Delete or disable** stale **`axiomfolio-frontend`** on Render~~ — **done** (dashboard deleted **2026-04-30**). | _(was)_ Small; avoided future static builds | — | — |
| 5 | After AxiomFolio repoint: ensure **`buildFilter`** / **`rootDir`** so **one** logical change does not always build **three** identical images if Render allows shared image (if not, accept 3× or consolidate workers). | **2×** duplicate Docker builds for same digest (heuristic) | Medium | Research Render “same commit” dedup; else document accept 3× |

---

## 5. Brain integration plan (spec only — **not implemented** in this PR)

Goal: Brain becomes the **ops “pimp daddy”** for Render quota — **proactive**, **durable**, **visible in Studio**.

### 5.1 Scheduler job: `render_quota_monitor`

- **Module:** new file `render_quota_monitor.py` under the Brain schedulers package (name follows existing snake_case jobs).
- **Schedule:** APScheduler **`IntervalTrigger`** every **6 hours** (or cron `0 */6 * * *` UTC — match [`infra-health.yaml`](../../.github/workflows/infra-health.yaml) spirit).
- **Gating:** Register in the same **`install(scheduler)`** pattern as [`infra_health.py`](../brain/app/schedulers/infra_health.py) / cost jobs. **Only** gate on **`BRAIN_SCHEDULER_ENABLED`** (must **not** introduce a new `BRAIN_OWNS_*` flag per direction).
- **Behavior:**
  1. If `BRAIN_SCHEDULER_ENABLED` is false → no-op (same process-level behavior as today).
  2. Load `RENDER_API_KEY` from settings.
  3. **Usage pull (priority order):**
     - Try **documented** Render REST resources for workspace or owner **pipeline / bandwidth / unbilled** totals (re-validate paths; `/v1/owners/{id}/usage` was **404** at audit time).
     - **Fallback:** enumerate all services (`/v1/services`), paginate **`/deploys`**, filter to **current calendar month** (or rolling 30d — **pick one** and store in snapshot), sum **durations** as in §Methodology → `pipeline_minutes_used_derived`.
  4. Persist a **`RenderQuotaSnapshot`** row (see §5.2).
  5. **Alert:** If `pipeline_minutes_used / pipeline_minutes_included > 0.80` **and** no open issue with label set `{infra-alert, render-quota}` (or last comment older than 7 days), **create** an issue **or** **comment** on the canonical tracking issue.
  6. **GitHub pattern:** reuse internal helper style of [`create_github_issue`](../../apis/brain/app/tools/github.py) / httpx GitHub REST — **conceptually similar** to workflow steps that call `github.rest.issues.createComment` (e.g. **Vercel promote** job in [`.github/workflows/vercel-promote-on-merge.yaml`](../../.github/workflows/vercel-promote-on-merge.yaml) lines ~363–385 — PR **#321** referenced by founder for GraphQL/REST commentary patterns). Prefer **`issues.create`** with labels **`infra-alert`**, **`render-quota`**; idempotency via label search.

### 5.2 SQLAlchemy model: `RenderQuotaSnapshot`

**Table name:** `render_quota_snapshots` (snake plural).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID / bigserial | PK |
| `recorded_at` | timestamptz UTC | Job completion time |
| `month` | char(7) | `YYYY-MM` billing alignment |
| `pipeline_minutes_used` | float | From API **or** derived sum |
| `pipeline_minutes_included` | float | e.g. **500** / workspace tier |
| `bandwidth_gb_used` | float | nullable if unavailable |
| `bandwidth_gb_included` | float | nullable |
| `unbilled_charges_usd` | numeric | nullable |
| `extra_json` | JSONB | raw Render payloads, service counts, derivation notes |

Index `(month DESC, recorded_at DESC)` for dashboards.

### 5.3 HTTP endpoint (Studio-ready)

- **`GET /api/v1/admin/render-quota`**
- **Auth:** Same as existing admin routes — **`X-Brain-Secret`** header vs `BRAIN_API_SECRET` (see [`admin.py`](../../apis/brain/app/routers/admin.py) `_require_admin`).
- **Response shape (JSON):**

```json
{
  "ok": true,
  "data": {
    "snapshot": {
      "recorded_at": "2026-04-28T12:00:00Z",
      "month": "2026-04",
      "pipeline_minutes_used": 1078.0,
      "pipeline_minutes_included": 500.0,
      "usage_ratio": 2.156,
      "derived_from": "render_api_usage|deploy_sum",
      "bandwidth_gb_used": null,
      "bandwidth_gb_included": null,
      "unbilled_charges_usd": null
    },
    "top_services_by_minutes": [
      {"service_id": "srv-...", "name": "filefree-api", "approx_minutes": 399.0}
    ]
  }
}
```

Studio **`/admin/infrastructure`** consumes **`data`** for a **quota panel** (progress bar + link to Render billing).

---

## 6. What success looks like

1. By **end of next calendar month**, **included Render pipeline minutes are not exceeded** — or overage is **known within 48 hours** via Brain **`render-quota`** visibility, not invoice surprise.
2. **Leading indicator:** **average daily derived pipeline minutes &lt; ~16/day** (~480/month toward a **500** included tier), tracked from **`RenderQuotaSnapshot`** deltas.
3. **brain-api** stays **`live`** on merges — **`update_failed`** spikes treated as **P1 infra** because they **directly burn quota** and starve prod deploys.

---

## Appendix — audit artifacts

- **API audit timestamp:** `now_iso`: **2026-04-28T03:42:11.304088+00:00** (UTC).
- **brain-api failure examples:** deploy ids **`dep-d7o0o0ek1jcs739rmqq0`**, **`dep-d7o0d5navr4c73flbia0`**, **`dep-d7o07a6gss3c73fckrjg`** (see §3a).
