# Wave 1 audit: Conversations + threaded replies

## TL;DR

The Conversations stack is **operationally wired** for create, list-with-filters (status/search/product), SSR load in Studio, founder replies via `POST …/messages`, and **optional** persona synthesis via **`POST …/persona-reply`** (litellm + YAML-backed `PersonaSpec`). Evidence also shows meaningful **architecture gaps**: Postgres `conversations` / `conversation_messages` from Alembic 012 are a **mirror** for persona replies, while the **canonical thread store is JSON + SQLite FTS5** (`apis/brain/app/services/conversations.py`). **`ea.mdc`-style smart routing on thread replies is not implemented** on the Conversation path (`append_message` only persists; `route_persona` is used in `app/services/agent.py`, not in the conversations router). Inline thread persona reply is **feature-flagged off** and the proxied Brain endpoint **`/admin/conversations/{id}/reply` does not exist** on Brain. Live listing of conversations in prod was **not authenticated** from this environment (`.env.secrets` not readable here; unauthenticated call returns 401 as expected).

## Findings

### 1. DB schema

- [✓] **`conversations` table (Postgres)** — evidence: `apis/brain/alembic/versions/012_conversations.py` lines 15–26 (`CREATE TABLE IF NOT EXISTS conversations (...)`).
- [✓] **`conversation_messages` table with FK** — evidence: same file lines 27–40 (`conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE`).
- [✓] **Index on `conversation_id`** — evidence: same file lines 42–47 (`CREATE INDEX IF NOT EXISTS conversation_messages_conversation_id_idx ON conversation_messages (conversation_id)`).
- [⚠] **Indexes on `tags`, `urgency`, `persona`, `created_at`** — Postgres mirror schema has **no** `tags`, `urgency`, or `persona` columns (only `id`, `title`, `created_at`, `updated_at`, `metadata`). Evidence: `apis/brain/app/models/conversation_mirror.py` lines 23–37 (`ConversationRecord`). No btree indexes declared beyond PK/FK in 012 migration.
- [⚠] **Canonical persistence vs Postgres** — evidence: `apis/brain/app/services/conversations.py` lines 1–5 (“Persistence: JSON files at apis/brain/data/conversations/&lt;id&gt;.json with a sidecar SQLite FTS5 index…”). `apis/brain/app/services/conversation_persona_reply.py` lines 128–177 (`mirror_persona_message_to_pg`) writes **mirror** rows after persona reply.

### 2. Backend create + list

- [✓] **`POST` create handler** — evidence: `apis/brain/app/routers/conversations.py` lines 147–159 (`@router.post("/conversations")` → `conv_svc.create_conversation`); mounted at `/api/v1/admin/...` via `apis/brain/app/main.py` lines 229–230 (`app.include_router(conversations.router, prefix="/api/v1")`).
- [✓] **`GET` list handler** — evidence: `apis/brain/app/routers/conversations.py` lines 70–101 (`list_conversations` → `conv_svc.list_conversations` with `filter`, `search`, `cursor`, `limit`, `product_slug`).
- [⚠] **Filtering by tag / urgency / persona** — `list_conversations` service supports **status_filter**, **search** (FTS), **organization_id**, **product_slug** only. Evidence: `apis/brain/app/services/conversations.py` lines 384–426 (parameters and filtering loop). No query params for `tags`, `urgency`, or `persona` on the router (`apis/brain/app/routers/conversations.py` lines 70–88).
- [✓] **`POST /admin/conversations/{id}/messages`** — evidence: `apis/brain/app/routers/conversations.py` lines 192–207 (`append_message` returns `success_response(msg.model_dump(...), status_code=201)`).

### 3. Frontend rendering

- [✓] **Studio route exists (`/admin/conversations` resolves to Brain conversations)** — evidence: `apps/studio/src/app/admin/conversations/page.tsx` lines 3–4 (`export { default } from "../brain/conversations/page"`).
- [✓] **Implementing UI** — `apps/studio/src/app/admin/brain/conversations/page.tsx`, `apps/studio/src/app/admin/brain/conversations/conversations-client.tsx`.
- [✓] **List sorted by recent activity** — evidence: `apis/brain/app/services/conversations.py` lines 429–430 (`convs.sort(key=lambda c: c.updated_at, reverse=True)`).
- [✓] **Thread shows message history from loaded conversation** — evidence: UI loads full conversation via `GET` after posts (`conversations-client.tsx` e.g. lines 752–753, 796–798 after `append_message`); conversation model includes `messages` (`apis/brain/app/schemas/conversation.py` lines 52–61).
- [✓] **Compose reply posts to messages endpoint** — evidence: `apps/studio/src/app/admin/brain/conversations/conversations-client.tsx` lines 782–791 (`apiFetch(\`/api/admin/conversations/${selected.id}/messages\`, { method: "POST", ... })`).
- [✓] **Next.js proxy to Brain** — evidence: `apps/studio/src/app/api/admin/conversations/route.ts` lines 23–31 (forwards to `${auth.root}/admin/conversations` with `X-Brain-Secret`); `apps/studio/src/lib/brain-admin-proxy.ts` lines 11–14 (Brain base URL is `{BRAIN_API_URL}/api/v1` when configured).
- [⚠] **Inline thread persona reply path** — `BRAIN_CONVERSATION_INLINE_PERSONA_REPLY_READY = false` (`conversations-client.tsx` line 290); handler early-returns (`lines 812–813`). When enabled, would call `POST /api/admin/conversations/{id}/reply` (`lines 837–844`), which proxies to a **non-existent** Brain route per `apps/studio/src/app/api/admin/conversations/[id]/reply/route.ts` lines 8–10 (TODO: Brain does not expose `POST .../reply`).

### 4. Persona routing

- [✗] **Automatic smart router on thread reply** — `append_message` only appends a `ThreadMessage` (`apis/brain/app/services/conversations.py` lines 448–472); no call to `route_persona` or `agent.process`.
- [⚠] **Tag + content + parent routing per `ea.mdc`** — not found on the Conversations API path. UI adds a **markdown prefix** when `@mentions` exist: `prependPersonaRoutingLine` (`apps/studio/src/app/admin/brain/conversations/conversations-client.tsx` lines 68–72). That is **not** server-side routing.
- [⚠] **`route_persona` usage** — evidence: `apis/brain/app/services/agent.py` lines 321–331 (`route_persona(message, channel_id=channel_id, persona_pin=effective_pin)`) inside `process()` — **Brain agent loop**, not `conversations` router.
- [⚠] **Persona LLM for `persona-reply`** — uses YAML `PersonaSpec` via `get_spec` and `_build_system_prompt(spec)` (`apis/brain/app/services/conversation_persona_reply.py` lines 70–78, 95–97, 205–208). Bundled `.mdc` persona text is loaded in **`agent.py`** (`apis/brain/app/services/agent.py` lines 52–60, 84–96, 357–361), **not** in `conversation_persona_reply.generate_persona_reply_text` (same file uses YAML-only system string at lines 110–117).
- [⚠] **“Request persona reply” payload** — Studio sends JSON with **`persona_slug` only** (`conversations-client.tsx` lines 868–872); `PersonaReplyRequest.message` defaults in schema (`apis/brain/app/schemas/conversation.py` lines 124–133), so routing context is largely the **default prompt**, not founder-typed intent.

### 5. Mobile experience

- [✓] **PWA / push plumbing present** — `apps/studio/public/sw.js` (e.g. `push` listener at lines 83+ per grep); subscription helpers `apps/studio/src/lib/web-push.ts` lines 17–50 (`serviceWorker.register("/sw.js")`, `pushManager.subscribe`); `apps/studio/src/components/pwa/PushSubscribeCard.tsx` lines 50–54 (fetches `/api/admin/web-push/vapid-public-key`).
- [✗] **Prove push works end-to-end in prod** — not verified here (would require subscribed client + Brain VAPID + delivery); only code paths documented.
- [⚠] **375px responsiveness (code inspection only, no browser run)** — list/thread uses `md:flex` / `hidden` patterns for stacked layout (`conversations-client.tsx` lines 1103–1104, 1206–1218). No automated visual proof in this audit.

### 6. End-to-end smoke

- [✓] **Prod Brain health reachable** — `GET https://brain.paperworklabs.com/api/v1/health` returned `{"success":true,"data":{"status":"ok","service":"brain","version":"0.1.0"}}` (HTTP 200) when fetched during the audit.
- [✓] **Admin list requires secret header** — `GET https://brain.paperworklabs.com/api/v1/admin/conversations?limit=1` without `X-Brain-Secret` returned HTTP **401** with body `{"detail":"Admin access required"}` (curl during audit).
- [?] **List recent conversations with credentials** — `.env.secrets` at repo root is **not readable in this Cursor workspace** (tooling blocked by ignore rules). Attempted `source ./.env.secrets` in a subshell did not expose `BRAIN_API_URL` / `BRAIN_API_SECRET` to the test process (likely non-exporting format or different key names); **no authenticated list result obtained**.
- [⚠] **`ea.mdc` curl example vs implementation** — runtime admin auth for these routes is **`X-Brain-Secret`** (`apis/brain/app/routers/conversations.py` lines 55–62), not `Authorization: Bearer $BRAIN_API_SECRET` as stated in the audit prompt. Optional Bearer is resolved as **Clerk JWT or env fallback org** (`apis/brain/app/dependencies/auth.py` lines 24–86).

## Gap list (machine-readable for Wave 2 ticket creation)

```yaml
gaps:
  - id: conv-gap-1
    severity: high
    surface: routing
    description: Thread founder replies do not trigger server-side persona routing or LLM; only optional explicit persona-reply endpoint runs litellm.
    evidence: "apis/brain/app/services/conversations.py:448-472; apis/brain/app/routers/conversations.py:192-207"

  - id: conv-gap-2
    severity: high
    surface: backend
    description: Postgres conversations schema is mirror-only; canonical threads live on disk JSON + FTS, diverging from Alembic 012 narrative and complicating backups/query.
    evidence: "apis/brain/app/services/conversations.py:1-5; apis/brain/alembic/versions/012_conversations.py:15-40"

  - id: conv-gap-3
    severity: medium
    surface: backend
    description: GET list API cannot filter server-side by tag, urgency, or persona (ea.mdc tag-directory workflows not first-class).
    evidence: "apis/brain/app/services/conversations.py:384-426; apis/brain/app/routers/conversations.py:70-88"

  - id: conv-gap-4
    severity: medium
    surface: frontend
    description: Studio proxies POST …/reply but Brain implements persona-reply and messages only; inline thread persona path is additionally disabled by feature flag.
    evidence: "apps/studio/src/app/api/admin/conversations/[id]/reply/route.ts:8-10; apps/studio/src/app/admin/brain/conversations/conversations-client.tsx:290,812-813,837-844"

  - id: conv-gap-5
    severity: medium
    surface: routing
    description: Persona replies in Conversation use YAML PersonaSpec system prompt, not bundled .cursor/rules *.mdc like the main Brain agent loop.
    evidence: "apis/brain/app/services/conversation_persona_reply.py:70-117; apis/brain/app/services/agent.py:357-361"

  - id: conv-gap-6
    severity: low
    surface: mobile
    description: Responsive layout patterns exist but 375px behavior was not runtime-verified in this audit.
    evidence: "apps/studio/src/app/admin/brain/conversations/conversations-client.tsx:1103-1104,1206-1218"

  - id: conv-gap-7
    severity: low
    surface: frontend
    description: Ops docs mention conversations-persona.sh wrapper; script not present under scripts/ in repo snapshot searched.
    evidence: ".cursor/rules/ea.mdc (expected wrapper); glob scripts/**/conversations*.sh -> 0 files"
```
