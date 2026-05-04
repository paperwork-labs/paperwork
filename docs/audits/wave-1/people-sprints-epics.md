# Wave 1 audit: People + Sprints + Epics + Goals

## TL;DR

**People** — **Partial**: `employees` table and full Brain CRUD under `GET|POST|PATCH /api/v1/admin/employees` exist and are admin-secret gated; Studio `/admin/people` loads the roster from Brain. Cross-links to “epics I own” are implicit via `owner_employee_slug` on epics and dispatch/activity timelines, not a dedicated profile surface. **Persona ↔ employee** is bridged through the Workspace tab (rules/personas), not a formal FK.

**Sprints** — **Split / partial**: SQL `sprints` rows with `start_date`, `end_date`, `status` exist (`apis/brain/app/models/epic_hierarchy.py:93–122`, migration `apis/brain/alembic/versions/009_epic_hierarchy.py:62–74`). Brain exposes `GET|POST|PATCH|DELETE /api/v1/admin/sprints` (`apis/brain/app/routers/epics.py:306+`). **Studio does not ship a dedicated sprints overview**: `next.config.mjs` permanently redirects `/admin/sprints` to `/admin/workstreams?tab=sprints` (lines 44–53), but the workstreams page only registers tabs `tree` and `pr-pipeline` (`apps/studio/src/app/admin/workstreams/page.tsx:52–63, 84`), so `tab=sprints` is ignored and collapses to the default `tree` (`apps/studio/src/components/layout/TabbedPageShellNext.tsx:107–108`). **`SprintsOverviewTab`** (`apps/studio/src/app/admin/sprints/sprints-overview-tab.tsx:115`) and **`CyclesBoardTab`** (`apps/studio/src/app/admin/sprints/cycles-board-tab.tsx:47`) are **not imported anywhere** outside their defining files (repo-wide grep). Markdown-tracked sprints (`docs/sprints/*.md`) still drive `SprintsOverviewTab` via `loadTrackerIndex()` — a third “sprint” concept beside SQL and JSON workstreams.

**Epics** — **Partial**: SQL `epics` with `title`, `status`, `owner_employee_slug`, `brief_tag`, `percent_done`, `related_plan`, optional `goal_id` and `product_slug` (`epic_hierarchy.py:55–90`, Alembic `009`, `013_epic_product_slug.py`). CRUD at `/api/v1/admin/epics` (`epics.py:168+`). Studio “Epics” nav points to **`/admin/workstreams`** (`apps/studio/src/lib/admin-navigation.tsx:70`), which renders an **expandable hierarchy tree** (`EpicsTreeView`) plus inline CRUD — **not** a kanban. **Dispatcher uses DB epics** (`apis/brain/app/schedulers/workstream_dispatcher.py:57–58`); **hourly progress snapshots still iterate `workstreams.json`** (`apis/brain/app/services/workstream_progress.py:69–72`), so `percent_done` drift between JSON and Postgres is a structural risk.

**Goals** — **Split brain**: (A) **Studio `/admin/goals`** reads/writes **`apis/brain/data/goals.json`** through `GET|POST|PUT|PATCH|DELETE /api/v1/admin/okr/goals` (`apis/brain/app/routers/admin.py:2190+`; `apps/studio/src/app/admin/goals/page.tsx:15–18`, `actions.ts:12`). (B) **SQL `goals` table** backs **`GET|POST|PATCH|DELETE /api/v1/admin/goals`** on the **epics router** (`apis/brain/app/routers/epics.py:47+`) and powers `getEpicHierarchy()` (`apps/studio/src/lib/brain-client.ts:796–800`). These two “goals” systems are **not unified** in the UI. (C) **`docs/strategy/OBJECTIVES.yaml`** is a separate strategic manifest surfaced only as **`GET /api/v1/admin/strategic-objectives`** summary (`admin.py:1524–1529`), not the Goals page.

**Workstreams board** — **Mostly legacy JSON at runtime UI**: Bundled `apps/studio/src/data/workstreams.json` has **77** workstreams (**53** `completed`, **2** `in_progress`, **6** `pending`; counted locally from HEAD). Brain serves live JSON via `GET /api/v1/admin/workstreams-board` using **`load_workstreams_file`** (disk JSON) (`admin.py:309–336`). **`load_epics_from_db`** is **used by the dispatcher** (`workstream_dispatcher.py:25,57`) but **not** by `workstreams-board`, progress snapshots, sprint auto-close board checks, or the current `/admin/workstreams` React page. **Drag board `WorkstreamsBoardClient`** (`workstreams-client.tsx:85`) appears **only in unit tests** — the page shell no longer mounts it. **`loadStudioWorkstreamsBoard`** (`cycles-data.ts:67`) has **no importers** in `apps/studio` besides its own file — dead export.

## Findings

### People (6 dimensions)

1. **DB table** — ✓ **`employees`** (`apis/brain/app/models/employee.py:22–23`). Rich schema: `kind`, org fields, Cursor config, `owned_*` JSON arrays, etc. (`employee.py:25–76`). Migration: `alembic/versions/008_employees.py` (referenced from employee model docstring chain).

2. **Backend CRUD** — ✓ **List, get, create, patch**, activity endpoint (`apis/brain/app/routers/employees.py:98–105`, `207–216`, `219–266`, `296–319`, `119–204`). **Auth**: `_require_admin` via `X-Brain-Secret` HMAC (`employees.py:33–38`). No `DELETE` observed in excerpt; treat as partial if hard-delete required.

3. **Studio page** — ✓ **`/admin/people`** (`apps/studio/src/app/admin/people/page.tsx:51–65`), nav (`admin-navigation.tsx:63`). Profile detail **`/admin/people/[slug]`** (`people/[slug]/page.tsx`).

4. **Cross-links** — ⚠ **Partial**. Activity links dispatches to generic **`/admin/workstreams`** with epic id in subtitle (`employee-profile-tabs-client.tsx:84–100`) — not epic-detail deep links. **`owner_employee_slug`** on goals/epics is the data link (`epic_hierarchy.py:35,64`). Personas: Workspace toggle loads `PersonasTabsClient` (`page.tsx:58–61`).

5. **Real data** — ? **Environment-dependent**. Committed JSON/goals files are seeded; **roster rows are not in git** — production/local DB must be inspected. No automated row-count in this audit.

6. **Mobile** — ⚠ **Unverified in device lab**. Layout uses responsive patterns (`people/page.tsx:22` `max-w-7xl`, `md:px-6`; org grid links `max-w-lg` / `min-w-0` in `employee-org-grid.tsx:86,132`). Treat as “likely OK” not proven.

### Sprints (6 dimensions)

1. **DB table** — ✓ **`sprints`** with `start_date`, `end_date`, `status`, `ordinal`, `lead_employee_slug`, `metadata` (`epic_hierarchy.py:93–122`).

2. **Backend CRUD** — ✓ **`/api/v1/admin/sprints`** (`epics.py:306+`).

3. **Studio page** — ✗ **Broken redirect / missing UI**. `/admin/sprints` → `/admin/workstreams?tab=sprints` (`next.config.mjs:50–53`) but workstreams tabs **do not include `sprints`** (`workstreams/page.tsx:52–63`). **`SprintsOverviewTab` not mounted** (no imports). **E2E** `e2e/admin-cycles.spec.ts` expects a “Cycles” tab on `/admin/sprints` flow — **would not match current `page.tsx` tab list** (test may skip on 404 only).

4. **Cross-links** — ⚠ **SQL**: sprint → epic via `epic_id` FK (`epic_hierarchy.py:99–102`). Studio tree shows nested sprints under epics when hierarchy loads. **No** dedicated sprint list page tied to DB.

5. **Real data** — ? SQL sprint **row counts are DB-specific**. Separate: **tracker / markdown sprints** for `SprintsOverviewTab` (`sprints-overview-tab.tsx:116` `loadTrackerIndex()`).

6. **Mobile** — ✗ **N/A** (primary UI not shipped). Markdown sprint UI components use stacked layouts where they exist; not validated.

### Epics (6 dimensions)

1. **DB table** — ✓ **`epics`** with fields aligning to user checklist (`epic_hierarchy.py:55–90`). **`product_slug`** added in migration `013_epic_product_slug.py`.

2. **Backend CRUD** — ✓ **`/api/v1/admin/epics`** (`epics.py:168+`).

3. **Studio page** — ✓ **`/admin/workstreams`** branded “Epics” — **tree + CRUD modals**, not kanban (`workstreams/page.tsx:67–69`, `epics-tree-view.tsx`).

4. **Cross-links** — ⚠ **goal_id**, **sprints[]**, **`owner_employee_slug`**, **`brief_tag`** wired in API/schema (`epic_hierarchy.py`, `schemas/epic_hierarchy.py:156–175`). **`closes_workstreams`** is **not** an epic/PR field in Pydantic epic models — see deep-dive.

5. **Real data** — ? **DB-dependent**. JSON board: **77** ids in `workstreams.json` (local count). Status distribution skewed completed vs active.

6. **Mobile** — ⚠ Tree + modals are dense; **unverified** on 375px.

### Goals (6 dimensions)

1. **DB table** — ✓ **`goals`** ORM (`epic_hierarchy.py:24–51`) + Alembic `009_epic_hierarchy.py:21–35`.

2. **Backend CRUD** — ✓ **Two stacks**: SQL **`/admin/goals`** on epics router (`epics.py:47+`); file-backed **`/admin/okr/goals`** (`admin.py:2190+`).

3. **Studio page** — ✓ **`/admin/goals`** (`goals/page.tsx`; nav `admin-navigation.tsx:72`). **Does not** edit SQL OKR rows — uses **`getGoals` → `/admin/okr/goals`** (`brain-client.ts:790–792`). **`OBJECTIVES.yaml`** is **not** this page; Brain exposes **`/admin/strategic-objectives`** (`admin.py:1524–1529`).

4. **Cross-links** — ⚠ SQL goal → epic chain exists in hierarchy API, but **Studio OKR page does not consume SQL goals**, so **goal → epic → sprint chain is broken in the Goals UI**.

5. **Real data** — ✓ **Q2-shaped objectives** live in committed **`apis/brain/data/goals.json`** (e.g. `"quarter": "2026-Q2"`, lines 1–3 at HEAD). SQL goals: **environment DB**.

6. **Mobile** — ⚠ Goals client uses cards and progress bars (`goals-client.tsx`) — **unverified** on device.

### Workstreams board (6 dimensions)

1. **DB-backed AND/OR JSON** — **Both, depending on subsystem**: **Dispatcher + `load_epics_from_db`** (`workstreams_loader.py:148–158`) vs **board API + progress + sprint auto-close + writeback** on **`workstreams.json`** (`admin.py:321–336`, `workstream_progress.py:69`, `sprint_md_auto_close.py:160`, `workstream_progress_writeback.py:1–4`).

2. **`load_epics_from_db` in dispatcher** — ✓ **`workstream_dispatcher.py:25,57`**.

3. **Studio page** — ⚠ **`/admin/workstreams`** today = **Tree + PR Pipeline** only (`page.tsx:52–84`). **No drag board** mounted. Reorder API exists (`workstreams-client.tsx:216` → `POST /api/admin/workstreams/reorder`) but **client is test-only** for the board shell.

4. **Cross-links** — ⚠ **PRs**: `brief_tag` search in GitHub drives `percent_done` in **`workstream_progress`** (`workstream_progress.py:73–74`) for **JSON ids**. Epics tree links **`github_pr`** on tasks (`epics-tree-view.tsx:52–70`).

5. **Real data** — **JSON**: **77** rows, mostly completed (local counts above). **DB epics**: not compared in running env — **no guarantee** parity with JSON.

6. **Mobile** — ⚠ Board client (when used) had filters/strip UI (`workstreams-client.tsx:61–83`); **current page** is tree — **unverified**.

## Cross-link health

| Link | Status | Notes |
|------|--------|-------|
| SQL `goal` → `epics` | ✓ | FK `goal_id` (`epic_hierarchy.py:62–63`) |
| SQL `epic` → `sprints` | ✓ | FK `epic_id` (`epic_hierarchy.py:99–102`) |
| SQL `epic` → `tasks` | ✓ | Optional `sprint_id` (`epic_hierarchy.py:125–157`) |
| SQL `epic` → person | ✓ | `owner_employee_slug` (`epic_hierarchy.py:64`) |
| Studio OKR (`goals.json`) → SQL hierarchy | ✗ | Separate APIs; no shared UI key |
| Studio tree → OKR page | ✗ | No navigation/linking observed between `/admin/goals` and hierarchy |
| `OBJECTIVES.yaml` ↔ SQL epics | ✗ | YAML is summary-only route; not wired to epic CRUD |
| Person profile → owned epics list | ⚠ | Activity/dispatch only; no “My epics” query UI |
| Sprint markdown (`docs/sprints`) ↔ SQL sprints | ✗ | Different sources |
| JSON workstream `id` ↔ SQL `epic.id` | ⚠ | Intended parity; **dual loaders** risk drift |
| PR merge → close sprint via `closes_workstreams` | ⚠ | See deep-dive — checks **JSON board**, not DB |

**Cross-link gaps (broken + partial, counting distinct edges above):** **9** (✗ rows + ⚠ rows in table).

## `closes_workstreams` field deep-dive

**Where defined**

- **Sprint markdown frontmatter** in `docs/sprints/*.md`, not Epic Pydantic/DB columns. Parser expects YAML list under key **`closes_workstreams`** (`apis/brain/app/services/sprint_md_auto_close.py:183–185`).
- **`docs-snapshot.json`** embeds `closes_workstreams: []` in some doc payloads — documentation mirror, not runtime.
- **Epic / PR outcome JSON** models **do not** define `closes_workstreams` (`schemas/epic_hierarchy.py`, `schemas/pr_outcomes.py` — no such field in epic response at `schemas/epic_hierarchy.py:156–175`).

**Where it is parsed**

- **`collect_sprint_auto_close_updates`** (`sprint_md_auto_close.py:149–207`): reads each sprint `.md`, extracts frontmatter (`_split_frontmatter`, lines 58–68), loads **`closes_workstreams`** via `_coerce_ws_id_list` (lines 94–101, 185).
- **Scheduled job** **`sprint_md_auto_close`** (`apis/brain/app/schedulers/sprint_completion.py:32–40, 97+`) runs the collector and opens a GitHub PR with updated frontmatter.

**What is “broken” / mismatched vs user expectation**

- **Not PR-body parsing**: Nothing in `pr_outcome_recorder.py` / merge webhooks grep-matches `closes_workstreams`. Closing is **doc frontmatter + conditions**, not “PR merged ⇒ parse tag”.
- **Completion source is `workstreams.json`**, not Postgres epics: `load_workstreams_file(bypass_cache=True)` (`sprint_md_auto_close.py:27,160–165`) builds `by_id` for `_all_workstreams_completed` (lines 135–146). If the board of record moves to **DB-only** but JSON stalls, **`closes_workstreams` gates never succeed**.
- **`_coerce_ws_id_list`** returns **empty** if YAML is not a list (`sprint_md_auto_close.py:94–96`) — malformed frontmatter silently drops IDs (no close).
- Tests lock expected behavior: `apis/brain/tests/test_sprint_completion.py` (module docstring line 1 names both `closes_pr_urls` and `closes_workstreams`).

## Gap list

```yaml
gaps:
  - id: company-data-gap-1
    severity: high
    entity: sprints
    surface: frontend
    description: >-
      /admin/sprints redirects to a non-existent workstreams tab; SprintsOverviewTab and CyclesBoardTab are never mounted.
    evidence: "apps/studio/next.config.mjs:50-53; apps/studio/src/app/admin/workstreams/page.tsx:52-84; sprints-overview-tab.tsx:115 (no imports)"
    fix_size: M

  - id: company-data-gap-2
    severity: critical
    entity: goals
    surface: cross-link
    description: >-
      Two goal systems (SQL hierarchy vs goals.json OKR) are not unified; Studio /admin/goals only uses the JSON file.
    evidence: "apps/studio/src/lib/brain-client.ts:790-800; apis/brain/app/routers/admin.py:2190-2229; apis/brain/app/routers/epics.py:47-85"
    fix_size: L

  - id: company-data-gap-3
    severity: high
    entity: workstreams
    surface: cross-link
    description: >-
      Dispatcher reads epics from Postgres but hourly progress + workstreams-board + sprint auto-close still use workstreams.json, allowing DB/JSON drift.
    evidence: "apis/brain/app/schedulers/workstream_dispatcher.py:57; apis/brain/app/services/workstream_progress.py:69; apis/brain/app/routers/admin.py:321-336; apis/brain/app/services/sprint_md_auto_close.py:160"
    fix_size: L

  - id: company-data-gap-4
    severity: medium
    entity: workstreams
    surface: frontend
    description: >-
      Drag-reorder board (WorkstreamsBoardClient) is not mounted on /admin/workstreams; loadStudioWorkstreamsBoard is unused.
    evidence: "apps/studio/src/app/admin/workstreams/page.tsx (no WorkstreamsBoardClient); cycles-data.ts:67 (no importers)"
    fix_size: M

  - id: company-data-gap-5
    severity: medium
    entity: epics
    surface: cross-link
    description: >-
      closes_workstreams gates sprint closure against JSON workstream status, not SQL epic status, so automation may disagree with DB truth.
    evidence: "apis/brain/app/services/sprint_md_auto_close.py:160-196"
    fix_size: M

  - id: company-data-gap-6
    severity: low
    entity: people
    surface: frontend
    description: >-
      No dedicated “epics owned by this employee” view; only indirect activity links to /admin/workstreams.
    evidence: "apps/studio/src/app/admin/people/[slug]/employee-profile-tabs-client.tsx:84-100"
    fix_size: S

  - id: company-data-gap-7
    severity: medium
    entity: goals
    surface: cross-link
    description: >-
      Strategic OBJECTIVES.yaml is exposed only via /admin/strategic-objectives, not linked from Studio Goals & OKRs page.
    evidence: "apis/brain/app/routers/admin.py:1524-1529; apps/studio/src/app/admin/goals/page.tsx:9-18"
    fix_size: M
```

## "Implemented but not wired" call-outs

1. **`SprintsOverviewTab`** — full UI in `apps/studio/src/app/admin/sprints/sprints-overview-tab.tsx` (export line 115); **zero route imports**.
2. **`CyclesBoardTab`** — `apps/studio/src/app/admin/sprints/cycles-board-tab.tsx:47`; **zero route imports**.
3. **`loadStudioWorkstreamsBoard`** — `apps/studio/src/lib/cycles-data.ts:67`; **no consumers** in `apps/studio`.
4. **`WorkstreamsBoardClient` / drag reorder** — implemented `workstreams-client.tsx:85+`; **only referenced from tests** (`workstreams/__tests__/workstreams-client.test.tsx`).
5. **Next.js redirect targets `tab=sprints` / `tab=cycles`** — `next.config.mjs:44–53` vs **`TabbedPageShell` allowlist** missing those ids (`workstreams/page.tsx:52–63` vs `TabbedPageShellNext.tsx:105–108`).
6. **`load_epics_from_db`** — wired for **dispatcher** only (`workstream_dispatcher.py:57`); **not** for `workstreams-board`, `workstream_progress`, or `sprint_md_auto_close` board load.

**Count of “implemented but not wired” features (above list):** **6**

---

_Report: `docs/audits/wave-1/people-sprints-epics.md` — READ-ONLY audit, no code changes._
