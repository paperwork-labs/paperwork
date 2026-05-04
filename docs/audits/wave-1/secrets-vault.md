# Wave 1 audit: Secrets Vault

## TL;DR

Studio’s vault is **implemented soundly at the persistence and crypto layer**: a Neon `secrets` row store with **`encrypted_value` + `iv` + `auth_tag`**, **`aes-256-gcm`** in `apps/studio/src/lib/crypto.ts`, and **upsert/delete/list/reveal APIs** under `/api/secrets/*` with **Bearer or Basic auth** (`apps/studio/src/lib/secrets-auth.ts`). Brain can read/write the vault programmatically via `apis/brain/app/tools/vault.py` when `SECRETS_API_KEY` + `STUDIO_URL` are set. The **Infrastructure → Secrets tab** (`/admin/infrastructure?tab=secrets`; legacy **`/admin/secrets` redirects** per `apps/studio/src/app/admin/secrets/page.tsx`) provides **listing, masked preview + reveal/copy, Brain criticality/episodes overlay** when **`BRAIN_API_URL` + `BRAIN_INTERNAL_TOKEN`** power `apps/studio/src/app/api/brain/secrets/[...path]/route.ts`. **What breaks the founder’s rotation workflow**: the SPA **never calls vault write APIs** (no create/rotate/delete UI—only **`POST` via scripts/intake`**), **reveal** uses **`GET /api/admin/secrets/:id`** which **`authenticateSecretsRequest` treats like the machine API**—**no Clerk session fallback** (`apps/studio/src/app/api/admin/secrets/[id]/route.ts`)—so **browser reveal likely 401 in production unless Basic/Bearer is attached client-side**. **Drift automation** exists in **`apis/brain/app/schedulers/secrets_audit.py`** (`secrets_drift_audit` daily 03:00 America/Los_Angeles when `BRAIN_OWNS_SECRETS_DRIFT_AUDIT` defaults true in `apis/brain/app/config.py`) comparing vault vs **Vercel/Render** fingerprints in **`apis/brain/app/services/secrets_intelligence.py`** (`audit_drift`), **not GitHub Actions secrets**. **Separate** `secrets_drift` **operating-score audit runner** (`apis/brain/app/audits/secrets_drift.py`) remains a **stub**. **`brain_user_vault`** is **schema + SQLAlchemy model only** (`apis/brain/app/models/vault.py`); **no services import or mutate it**.

## Findings

### 1. DB schema + encryption

| Check | Status | Evidence |
| --- | --- | --- |
| `secrets` table in Studio DB | ✓ | `apps/studio/src/lib/db.ts` `ensureSecretsTable()` L17–31 — `encrypted_value TEXT NOT NULL`, `iv TEXT NOT NULL`, `auth_tag TEXT NOT NULL`, etc. **Runtime DDL** (Neon via `@neondatabase/serverless`), not Prisma migrations. |
| Alembic/Prisma for Studio `secrets` | ? | No `*.prisma`/`alembic` under `apps/studio/` for vault; authoritative schema is **`CREATE TABLE IF NOT EXISTS`** above. |
| IV / nonce for GCM | ✓ | `randomBytes(12)` — `apps/studio/src/lib/crypto.ts` L21–22. |
| Auth tag for GCM | ✓ | `cipher.getAuthTag()` persisted as `authTag` — L26–31, decrypted with `decipher.setAuthTag` L37–38. |
| Algorithm | ✓ | `const ALGORITHM = "aes-256-gcm"` — L3. |
| Key source | ✓ | `process.env.SECRETS_ENCRYPTION_KEY` base64, **32 bytes** enforced — `getKey()` L5–13. |
| Key validated on startup | ⚠ | **Lazy**: `getKey()` throws **on first encrypt/decrypt**, not Next.js boot (`apps/studio/src/lib/crypto.ts`). |
| Brain registry / episodes tables | ✓ | `apis/brain/alembic/versions/003_brain_secrets_intelligence.py` — `brain_secrets_registry`, `brain_secrets_episodes`. |

### 2. Backend CRUD

| Route / behavior | Status | Evidence |
| --- | --- | --- |
| `POST /api/secrets` (create/update) — auth | ✓ | `authenticateSecretsRequest` — **Bearer `SECRETS_API_KEY` or Basic admin** — `apps/studio/src/app/api/secrets/route.ts` L6–8, L26–28. |
| `GET /api/secrets` — metadata only | ✓ | Select omits ciphertext — **id, name, service, meta timestamps** — L12–17. |
| `GET /api/secrets/[id]` — decrypted value | ✓ | `decrypt(...)` returned in JSON — `apps/studio/src/app/api/secrets/[id]/route.ts` L34–52. |
| Structured audit trail for reveal/rotate | ? | Rotations bump `last_rotated_at` on upsert (`route.ts` POST L53–67); **no dedicated append-only audit table** surfaced in audited files. |
| `PATCH /api/secrets/[name]` | ✗ | **No PATCH handler** — updates are **`POST` upserts** (`ON CONFLICT`) — `route.ts` L53–66. |
| `DELETE /api/secrets/[id]` | ✓ | `DELETE` handler — `[id]/route.ts` L59–86. |
| `GET /api/admin/secrets/[id]` | ✓ | Same decrypt contract as `/api/secrets/[id]` + same **secrets-auth** — `apps/studio/src/app/api/admin/secrets/[id]/route.ts`. |
| Middleware: `/api/secrets` | ✓ | **Excluded from Clerk/Basic wall** — `apps/studio/src/middleware.ts` L74–80. |
| Middleware: `/api/admin/*` | ✓ | **Clerk or Basic in production** — L87–102. |

### 3. Studio UI

| Check | Status | Evidence |
| --- | --- | --- |
| Page exists | ✓ | **Tab**: `apps/studio/src/app/admin/infrastructure/tabs/secrets-tab.tsx` renders `SecretsClient`. **Legacy** `apps/studio/src/app/admin/secrets/page.tsx` **`permanentRedirect("/admin/infrastructure?tab=secrets")`**. E2E: `apps/studio/e2e/admin-routes.spec.ts`. |
| List + metadata | ✓ | Server loads rows from DB; client groups by **service**, shows **expires / last_rotated / updated** — `secrets-client.tsx` L635–648. |
| Brain criticality + last rotated | ⚠ | **Criticality badge** only when name matches **`brain_secrets_registry`** (`/api/brain/secrets/registry`) — L521–541. **`last_rotated_at` shown from Studio DB**, not Brain registry row in main list (Brain rotation line only inside **popover** optional field — **BrainNotesCard** L92–95). |
| Detail / masked value | ✓ | Hidden `••••` until reveal — L606–614; reveal shows **snippet** `previewSnippet` — L588–589. |
| **Rotate** button | ✗ | **No Rotate / edit / paste-new-value** controls in **`secrets-client.tsx`** — only Eye/Copy (`L620–631`). API reference lists **POST GET** etc. (**L671–674**) — **DELETE not listed in UI cheat sheet.** |
| Create flow from UI | ✗ | **No form** in `SecretsClient`; creation via **`POST /api/secrets`** (scripts) or **intake** (below). |
| “Cryptolink” first-time fill | ✓ | **Secret intake**: `POST /api/secrets/intake` returns URL; founder flow **`/admin/secrets/intake/[token]`** — `apps/studio/src/app/api/secrets/intake/route.ts`, `apps/studio/src/app/admin/secrets/intake/[token]/page.tsx`, submit `apps/studio/src/app/api/secrets/intake/[token]/submit/route.ts` (Clerk **admin email** gate L32–38 on submit). |

### 4. Brain overlay

| Check | Status | Evidence |
| --- | --- | --- |
| Overlay when env set | ✓ | Client `fetch("/api/brain/secrets/registry")` — `secrets-client.tsx` L248–264; popover loads episodes `.../episodes/${name}` — L139–141. |
| Proxy path | ✓ | `apps/studio/src/app/api/brain/secrets/[...path]/route.ts` → **`{BRAIN_API_URL}/internal/secrets/{path}`** with **`Authorization: Bearer {BRAIN_INTERNAL_TOKEN}`** L13–27. |
| Doc vs code token name | ⚠ | Runbook `docs/infra/BRAIN_SECRETS_INTELLIGENCE.md` L83 references **`BRAIN_INTERNAL_TOKEN`**; Studio admin elsewhere often uses **`BRAIN_API_SECRET`** for `/api/v1/admin/*` — **two different Brain auth channels**. |
| Registry model path | ✓ | `apis/brain/app/models/secrets_intelligence.py` → `brain_secrets_registry` (not `secret_registry.py`). |
| Drift detection location | ✓ | **`SecretsIntelligence.audit_drift`** — `apis/brain/app/services/secrets_intelligence.py` **L311–477**; scheduled **`_body_drift_audit`** — `apis/brain/app/schedulers/secrets_audit.py` **L72–101**. |

### 5. Rotation workflow

| Step | Wired? | Evidence |
| --- | --- | --- |
| 1. Founder opens vault UI | ✓ | `https://paperworklabs.com/admin/infrastructure?tab=secrets` (redirect from `/admin/secrets`). |
| 2. Opens a secret (“row”) | ✓ | List rows expand inline; **no separate detail route**. |
| 3. Rotate / paste new value in UI | ✗ | **No UI affordance** in `SecretsClient`. **Intake paste** exists on **`/admin/secrets/intake/:token`** (submit route upserts vault **L111–134**). **Scripts**: `vault-set.sh` pattern in `docs/SECRETS.md` / `.cursor/rules/secrets-ops.mdc`. |
| 4. Vault DB updated | ✓ | `POST /api/secrets` or intake submit **`ON CONFLICT DO UPDATE`** + **`last_rotated_at = now()`** — `route.ts` POST L53–67; intake submit L123–132. |
| 5. Vercel / Render / GitHub auto-updated | ✗ | **No automation** in audited paths pushes env to hosts; **`audit_drift` compares** fingerprints only. **GitHub Actions secrets**: **not compared** (Vercel + Render APIs only in `audit_drift` **L400–467**). |
| 6. Old value invalidated + audit record | ⚠ | **Old ciphertext replaced**; **Brain episode** **`rotation`** not emitted from Studio on generic `POST` (intake submit returns JSON **without** calling **`POST /internal/secrets/events`** — end of **`submit/route.ts` L158**). Brain **`/internal/secrets/events`** accepts events — **`apis/brain/app/api/secrets.py` L49–90**. |

### 6. Brain runtime usage

| Check | Status | Evidence |
| --- | --- | --- |
| `vault.py` exists | ✓ | `apis/brain/app/tools/vault.py` — `vault_list`, `vault_get`, `vault_set`; **`httpx.AsyncClient`** to **`settings.STUDIO_URL`** + Bearer **`settings.SECRETS_API_KEY`** L93–100. |
| Fetches secrets at runtime | ✓ | **Assumes Brain env has `SECRETS_API_KEY` + `STUDIO_URL`** configured (same pattern as **`credential_expiry`**). |
| **`brain_user_vault`** usage | ✗ | **Model only** — `apis/brain/app/models/vault.py`; exported in `models/__init__.py`. **Grep**: no service reads/writes table beyond migration `001_initial_schema.py`. |

### 7. Drift detection

| Check | Status | Evidence |
| --- | --- | --- |
| Scheduled vault vs Vercel/Render | ✓ | **`secrets_drift_audit`** — `secrets_audit.py` L199–212; **`install`** gated **`BRAIN_OWNS_SECRETS_DRIFT_AUDIT`** (default **True** — `config.py` L135). |
| Scheduled rotation reminders | ✓ | **`secrets_rotation_monitor`** 09:00 PT — `secrets_audit.py` L212–223; episodes **`rotation_due`**. |
| **`credential_expiry.py`** | ✓ | **Separate job**: **`GET /api/secrets`** (metadata incl. **`expires_at`**) daily **08:00 UTC**, posts **`Credential Expiry Report`** Conversation when within window — **`apis/brain/app/schedulers/credential_expiry.py`** L101–161. **Not** Vercel/Render fingerprint drift. |
| Results surfaced | ✓ | **Registry** **`drift_summary` / `drift_detected_at`** consumed in Studio **`BrainNotesCard`** (`secrets-client.tsx`). Episodes **`drift_detected`** written **`secrets_audit.py` L81–92**. Optional **Agent tasks** **`try_queue_agent_task`**. |
| Operating-score **`secrets_drift` audit** | ⚠ | **Stub** — `apis/brain/app/audits/secrets_drift.py` (“runner not yet implemented”). Distinct from APScheduler **`secrets_drift_audit`**. |

## Gap list

```yaml
gaps:
  - id: secrets-gap-1
    severity: critical
    surface: ui
    description: Vault UI exposes no create/rotate/delete; founder must use API, scripts, or intake token.
    evidence: apps/studio/src/app/admin/secrets/secrets-client.tsx — no POST/PATCH/DELETE controls (L362–689)
    fix_size: M

  - id: secrets-gap-2
    severity: high
    surface: ui
    description: Client reveal calls /api/admin/secrets/:id with secrets-auth only; browser fetch typically lacks Bearer/Basic, conflicting with Clerk-gated middleware.
    evidence: secrets-client.tsx L330; apps/studio/src/app/api/admin/secrets/[id]/route.ts L12-13 uses authenticateSecretsRequest (not Clerk session).
    fix_size: S

  - id: secrets-gap-3
    severity: medium
    surface: rotation
    description: No automatic propagation from Studio vault to Vercel, Render, or GitHub secrets after rotation.
    evidence: No push logic in apps/studio secret routes; drift compares only (secrets_intelligence.py L400–467).
    fix_size: L

  - id: secrets-gap-4
    severity: medium
    surface: brain-overlay
    description: Successful vault rotation / intake does not evidently POST Brain /internal/secrets/events for episodic timeline (intake submit ends at NextResponse JSON only).
    evidence: apps/studio/src/app/api/secrets/intake/[token]/submit/route.ts L158; apis/brain/app/api/secrets.py L49–90
    fix_size: S

  - id: secrets-gap-5
    severity: low
    surface: drift
    description: Scheduled drift compares Vercel and Render env only; GitHub Actions secrets matrix from doc intent is absent.
    evidence: BRAIN_SECRETS_INTELLIGENCE.md L91-93; secrets_intelligence.py audit_drift Vercel/Render sections only (L400–467)
    fix_size: M

  - id: secrets-gap-6
    severity: low
    surface: db
    description: Studio secrets schema applied via CREATE IF NOT EXISTS at runtime — no migration history in-repo for vault DDL evolution.
    evidence: apps/studio/src/lib/db.ts ensureSecretsTable
    fix_size: S

  - id: secrets-gap-7
    severity: low
    surface: brain-runtime
    description: Separate operating-score audit id secrets_drift is still a stub and can report misleading freshness vs real APScheduler drift job.
    evidence: apis/brain/app/audits/secrets_drift.py; apis/brain/app/services/audits.py registry id secrets_drift
    fix_size: XS

  - id: secrets-gap-8
    severity: low
    surface: backend
    description: SECRETS_ENCRYPTION_KEY mismatch is only detected on first encrypt/decrypt, not deploy-time.
    evidence: apps/studio/src/lib/crypto.ts getKey()
    fix_size: XS
```

## brain_user_vault decision (orchestrator action item)

**Recommendation: treat as unused schema — remove via Alembic (or formally freeze with KNOWLEDGE.md ADR)**. The **`brain_user_vault`** table and **`UserVault`** SQLAlchemy model exist (`apis/brain/alembic/versions/001_initial_schema.py`, `apis/brain/app/models/vault.py`), but **no repository, scheduler, MCP tool, or route references them** besides model export. Continuing to imply a “per-user encrypted vault” without read/write paths violates the **no silent capability** instinct: operators assume defenses that never run. Unless **Phase H** explicitly schedules **OAuth/API key escrow** with a named owner, **rip out** the table/model in a migrations-backed PR **or** add a single doc decision: **reserved, not wired** — with a checklist to delete if still zero rows after N months.

---

*Audit method: READ-ONLY codebase inspection; no prod calls, secret values, or PRs.*
