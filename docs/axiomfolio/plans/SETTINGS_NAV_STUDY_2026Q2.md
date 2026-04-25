---
owner: engineering
last_reviewed: 2026-04-22
doc_kind: plan
domain: design
status: active
---
# Settings IA Study — 2026 Q2

**Status:** Study only. Reorg ships as the PR immediately after J4B (this doc lands alongside J4B follow-up).

**Motivation:** The sidebar reorg (J4B) pushed "Settings" to the bottom rail and added role-aware `Cmd+,` jumps. The next question is whether the `/settings/*` left-rail itself is still coherent. It grew organically (AI keys, MCP tokens, historical import, account risk, admin sub-tree all landed as separate drops), and today's flat list mixes "touch once ever" items (data privacy) with "touch every week" items (connections). This doc inventories the current tree and proposes a clustered reorg.

## 1. Current `/settings/*` tree

Sources: `frontend/src/App.tsx` lines 267–288, `frontend/src/pages/SettingsShell.tsx` lines 74–131, `frontend/src/pages/Settings*.tsx`, `frontend/src/pages/settings/HistoricalImportWizard.tsx`.

### Routes today

| Route | Component file | Gate | Comment |
|---|---|---|---|
| `/settings` | (index → `profile`) | auth | Default redirect. |
| `/settings/profile` | `pages/SettingsProfile.tsx` | auth | Name, email, password, session. |
| `/settings/preferences` | `pages/SettingsPreferences.tsx` | auth | Theme, color-blind palette, density, currency, timezone. |
| `/settings/connections` | `pages/SettingsConnections.tsx` | auth | Broker connections (IBKR / Schwab / TastyTrade), FlexQuery tokens. |
| `/settings/historical-import` | `pages/settings/HistoricalImportWizard.tsx` | auth | One-time wizard for backfilling historical trades. |
| `/settings/account-risk` | `pages/SettingsAccountRisk.tsx` | auth | Per-account risk caps and position limits. |
| `/settings/ai-keys` | `pages/SettingsAIKeys.tsx` | auth | BYOK OpenAI / Anthropic / Gemini keys. |
| `/settings/mcp` | `pages/SettingsMCP.tsx` | auth | MCP server tokens for the Cursor integration. |
| `/settings/notifications` | `pages/SettingsNotifications.tsx` | auth | Email / push digest toggles. |
| `/settings/data-privacy` | `pages/SettingsDataPrivacy.tsx` | auth | DSAR export, delete-account, retention. |
| `/settings/admin/system` | `pages/SystemStatus.tsx` | owner/admin | Pipeline + Celery + Redis + DB health. |
| `/settings/admin/users` | `pages/SettingsUsers.tsx` | owner/admin | Invite / approve / role changes. |
| `/settings/admin/agent` | `pages/AdminAgent.tsx` | owner/admin | Agent capabilities + audit log. |
| `/admin/picks` | `pages/admin/PicksValidator.tsx` | owner/admin | Picks validator (rendered in Settings rail but lives outside `/settings`). |

### Observations

1. **Flat rail, no clustering.** The SettingsShell renders nine items under a single "Account" heading, which is accurate for only three of them. A new user who wants to connect a broker has to scan past Profile, Preferences, and then find Connections sandwiched before Account risk.
2. **Two "keys" surfaces.** AI Keys and MCP Tokens are conceptually different (LLM provider secrets vs agent-tool auth tokens) but visually indistinguishable. Users opening the wrong one is a known annoyance.
3. **Historical import is a transient wizard.** It occupies permanent rail real-estate for a one-shot flow. Belongs inside Connections (next to its related broker) or as a modal kicked off from Portfolio Import.
4. **Account risk sits in Account.** It is a **trading** configuration (position caps, heat ceilings) and should cluster with future Trading prefs, not with Profile / password.
5. **Picks validator is in the rail but routed outside `/settings`.** `SettingsShell` links to `/admin/picks`, which is a top-level route — breadcrumbs lie. Either move the route under `/settings/admin/picks` or drop it from the rail entirely.
6. **Data privacy and Notifications are "touch once" items** buried between high-churn items. They should drop into their own lower cluster.
7. **No role separation in the first view.** Admin links appear below a small `Admin` header but in the same visual weight, so non-admin vs admin rails look almost identical at a glance.

## 2. Proposed clusters

Order reflects expected frequency of use, not alphabetical order. Cluster headings show in the left rail with the same `uppercase / tracking-wider / text-muted-foreground` treatment already used.

| Order | Cluster | Items | Role |
|---|---|---|---|
| 1 | **Account** | Profile · Preferences | auth |
| 2 | **Connections** | Broker connections · Historical import (moved) | auth |
| 3 | **Trading** | Account risk (moved) · _Future: strategy defaults, paper mode toggle_ | auth |
| 4 | **Notifications** | Notifications | auth |
| 5 | **AI** | AI Keys · MCP tokens | auth |
| 6 | **Privacy** | Data privacy | auth |
| 7 | **Admin** | System Status · Users · Agent · Picks validator | owner / admin |

Rationale:

- **Account** is intentionally small (2 items). Signals "identity / appearance, rarely touched once set".
- **Connections** promotes the single most-used settings page into the second slot and folds Historical import inline because it only matters to someone who just connected a broker.
- **Trading** is a new cluster with only one member today (Account risk) but carries the right affordance for future additions (strategy defaults, paper-mode switch, portfolio heat cap).
- **AI** groups the two secrets surfaces so users stop hunting. Each page can keep its own sub-section inside a shared AI settings layout later.
- **Admin** stays last, visually separated by the existing divider.

## 3. Move list

### Relocations (no file moves, route-only)

| From | To | Why |
|---|---|---|
| `/settings/historical-import` | `/settings/connections/historical-import` | Belongs with broker flow. Keep old path as a `<Navigate replace>` for 1 release. |
| `/settings/account-risk` | `/settings/trading/account-risk` | New Trading cluster. |
| `/admin/picks` | `/settings/admin/picks` | Align route with where it already renders in the Settings rail. Keep `/admin/picks` as a `<Navigate replace>` for 1 release. |

### Rail-only changes (no route moves)

- Re-group `MenuLink`s inside `SettingsShell.tsx` around the 7 clusters above.
- Render cluster headings (`<p class="... uppercase">`) between groups, matching the current `Account` / `Admin` pattern.
- Keep existing icon mappings in the collapsed rail; reorder only.

### New routes (future, not in reorg PR)

- `/settings/trading/paper` — paper-mode toggle (queued behind shadow-trade work).
- `/settings/trading/heat` — portfolio heat ceiling editor (queued).

Neither is built yet; they are placeholders so the Trading cluster is not a cluster-of-one on day one.

### Deprecations

- None removed. Every current page has at least one active user flow. Intent is pure reorg, not retirement.

## 4. Non-goals

- **No content rewrites** in this reorg. Copy, field validation, and form layouts inside each page are untouched.
- **No tier gating changes.** Feature entitlements continue to be enforced at the API / `FeatureCatalog` layer; the Settings rail remains a navigation surface only.
- **No mobile-specific changes.** The collapsed 20px icon rail keeps its current ordering rules.

## 5. Acceptance criteria for the reorg PR

1. `SettingsShell.tsx` renders the seven clusters in the order above with role-aware gating on `Admin`.
2. Old deep links (`/settings/historical-import`, `/settings/account-risk`, `/admin/picks`) land on their new paths via `<Navigate replace>`.
3. Existing tests (`SettingsShell.test.tsx`, `SettingsConnections.test.tsx`, etc.) pass unchanged or are updated to reference the new group labels.
4. One new test asserts non-admin users do not see the Admin cluster.
5. No changes to component internals, just routes + rail grouping.

## 6. Sequencing

1. **J4B (shipped):** sidebar reorg, logo link, Cmd+K pill, Cmd+, role-aware, NotFound.
2. **J4B follow-up (this doc):** Cmd+, role-aware destination split, Cmd+K tooltip, settings IA study.
3. **J4C (next PR):** execute Section 3 above. Keeps diff under ~250 lines, no component rewrites, can ship in the same sprint as J4.

## 7. Open questions

- Should `Connections` include a read-only view of MCP tokens, or keep MCP cleanly under AI? Leaning: keep under AI, since MCP is an agent-tool concern, not a data-source.
- Should `Preferences` split into `Appearance` (theme, palette, density) and `Regional` (currency, timezone)? Not urgent; revisit if the page grows past ~10 fields.
- Does the Trading cluster warrant its own tab-inside-page shell (Risk / Defaults / Paper) on day one, or is a flat page fine until we have three items? Defer — premature nesting makes the empty state worse.
