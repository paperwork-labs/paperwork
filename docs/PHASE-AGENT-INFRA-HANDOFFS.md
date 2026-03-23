# Agent Infrastructure & Migration Handoff Prompts

Self-contained prompts for Cursor Composer. Each session creates a feature branch, commits, pushes, opens a PR.

**Pre-requisite**: Complete Phase A (manual setup) before running any Composer sessions.

**Quality routing**: Sessions 1-4 are Composer (mechanical, well-scoped). Sessions 5-8 are Opus (architecture, security, complex reasoning). Do NOT run Sessions 5-8 in Composer.

---

## Phase A: Manual Setup (No Composer Needed)

Do these first. They're dashboard clicks and account setup, not code.

### A.1 Create Paperwork Labs Vercel Team

1. Go to https://vercel.com/account → "Create Team" → name: "Paperwork Labs"
2. Transfer all 5 projects (filefree, launchfree, studio, trinkets, distill) to the team
3. On the filefree project: Settings → Domains → Add `filefree.ai` as primary domain
4. Add `www.filefree.ai` as redirect to `filefree.ai`
5. Keep `filefree.tax` as redirect domain (301 → filefree.ai)
6. On the studio project: Add `paperworklabs.com` domain (if not already)
7. On the launchfree project: Add `launchfree.ai` domain
8. On the distill project: Add `distill.tax` domain
9. On the trinkets project: Add `tools.filefree.ai` domain
10. Update Vercel API token in vault if it changed after team transfer

### A.2 Create Paperwork Labs Render Workspace

1. Go to https://dashboard.render.com → Create Team/Workspace → name: "Paperwork Labs"
2. Transfer `filefree-api` and `launchfree-api` services to the workspace
3. On `filefree-api`: Settings → Custom Domain → add `api.filefree.ai`
4. On `launchfree-api`: Settings → Custom Domain → add `api.launchfree.ai`
5. Verify health: `curl https://api.filefree.ai/health`

### A.3 DNS Configuration (at your registrar)

For **filefree.ai**:
- `filefree.ai` → CNAME `cname.vercel-dns.com` (or A record per Vercel instructions)
- `www.filefree.ai` → CNAME `cname.vercel-dns.com`
- `api.filefree.ai` → CNAME from Render custom domain setup

For **filefree.tax** (keep as redirect):
- Keep pointing to Vercel (it will 301 → filefree.ai after Vercel domain config)
- Remove old subdomains: `api.filefree.tax`, `n8n.filefree.tax`, `social.filefree.tax`

For **paperworklabs.com**:
- `paperworklabs.com` → CNAME `cname.vercel-dns.com` (Studio)
- `n8n.paperworklabs.com` → A record `204.168.147.100` (Hetzner, current as of March 2026 — verify in Hetzner console if server rebuilt)
- `social.paperworklabs.com` → A record `204.168.147.100` (Hetzner, same server)

For **launchfree.ai**:
- `launchfree.ai` → CNAME `cname.vercel-dns.com`
- `api.launchfree.ai` → CNAME from Render custom domain setup

For **distill.tax**:
- `distill.tax` → CNAME `cname.vercel-dns.com`

### A.4 Get API Keys

1. **Anthropic**: Go to https://console.anthropic.com → Create API key → Store in vault:
   ```bash
   curl -X POST https://paperworklabs.com/api/secrets \
     -H "Authorization: Bearer $SECRETS_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"name": "ANTHROPIC_API_KEY", "value": "sk-ant-...", "service": "anthropic", "location": "vault", "description": "Anthropic API key for Claude models in n8n workflows"}'
   ```
2. **Google Gemini**: Go to https://aistudio.google.com/apikey → Create API key → Store in vault:
   ```bash
   curl -X POST https://paperworklabs.com/api/secrets \
     -H "Authorization: Bearer $SECRETS_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"name": "GEMINI_API_KEY", "value": "...", "service": "google", "location": "vault", "description": "Gemini API key for Flash/Pro models in n8n workflows"}'
   ```
3. Wire both to n8n: SSH to Hetzner, add to `/opt/paperwork-ops/.env`, update `compose.yaml` environment section, `docker compose restart n8n`

### A.5 Install UI UX Pro Max Skill

1. Download from https://github.com/manuelisimo/ui-ux-pro-max (or wherever hosted)
2. Copy the skill file to `.cursor/rules/ui-ux-pro-max.mdc` or `.cursor/commands/ui-ux-pro-max.md`
3. Copy any data directory to `.shared/ui-ux-pro-max/` if the skill requires it

### A.6 Activate Context7 MCP

1. Open `.cursor/mcp.json` (create from `.cursor/mcp.json.example` if it doesn't exist)
2. Add (or uncomment) the context7 server:
   ```json
   "context7": {
     "command": "npx",
     "args": ["-y", "@upstash/context7-mcp@latest"]
   }
   ```
3. Restart Cursor

---

## Phase B: Composer Sessions

### Session 1: Turborepo Setup

**Copy everything below into Composer:**

```
## Task: Add Turborepo for Parallel Builds

Branch: `chore/turborepo-setup` (create from main)

### What to build

Add turbo.json to enable parallel builds, task caching, and proper dependency ordering across all 5 apps and 3 packages.

### Files to create/modify

1. **Create `turbo.json`** at repo root:

```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"],
      "env": [
        "NEXT_PUBLIC_API_URL",
        "NEXT_PUBLIC_POSTHOG_KEY",
        "NEXT_PUBLIC_POSTHOG_HOST"
      ]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "type-check": {
      "dependsOn": ["^build"]
    },
    "test": {
      "dependsOn": ["^build"]
    }
  }
}
```

2. **Update root `package.json`** scripts to use turbo:

Replace existing build/lint/test scripts with:
```json
{
  "scripts": {
    "build": "turbo run build",
    "dev": "turbo run dev",
    "lint": "turbo run lint",
    "type-check": "turbo run type-check",
    "test": "turbo run test",
    "dev:filefree": "turbo run dev --filter=@paperwork-labs/filefree",
    "dev:studio": "turbo run dev --filter=@paperwork-labs/studio",
    "dev:launchfree": "turbo run dev --filter=@paperwork-labs/launchfree",
    "dev:trinkets": "turbo run dev --filter=@paperwork-labs/trinkets",
    "dev:distill": "turbo run dev --filter=@paperwork-labs/distill"
  }
}
```

3. **Add turbo as a dev dependency**: `pnpm add -Dw turbo`

4. **Add `.turbo/` to `.gitignore`** (turbo cache dir)

5. **Verify each app's `package.json`** has proper `name` fields:
   - `apps/filefree/package.json` → `"name": "@paperwork-labs/filefree"`
   - `apps/studio/package.json` → `"name": "@paperwork-labs/studio"`
   - `apps/launchfree/package.json` → `"name": "@paperwork-labs/launchfree"`
   - `apps/trinkets/package.json` → `"name": "@paperwork-labs/trinkets"`
   - `apps/distill/package.json` → `"name": "@paperwork-labs/distill"`
   - `packages/ui/package.json` → `"name": "@paperwork-labs/ui"`
   - `packages/auth/package.json` → `"name": "@paperwork-labs/auth"`
   - `packages/analytics/package.json` → `"name": "@paperwork-labs/analytics"`

6. **Verify each app's `package.json`** has these scripts (add if missing):
   - `"build": "next build"` (all apps)
   - `"dev": "next dev --port XXXX"` (with correct port per app)
   - `"lint": "next lint"` or `"eslint ."` (whatever exists)
   - `"type-check": "tsc --noEmit"` (all TypeScript apps)

7. **Update CI** (`.github/workflows/ci.yaml`): The existing CI already runs per-path jobs. No turbo changes needed in CI yet (turbo is primarily for local dev speed). But verify the build matrix still works by checking that `pnpm run build --filter=@paperwork-labs/filefree` works.

8. **Update Makefile**: If `make dev`, `make build`, `make lint` exist, update them to use the new turbo-based root scripts.

### Acceptance criteria

- `pnpm turbo run build` builds all 5 apps + 3 packages in parallel
- `pnpm turbo run build --filter=@paperwork-labs/filefree` builds only FileFree + its dependencies
- `pnpm turbo run type-check` runs TypeScript checks across all apps
- Second build is faster (turbo cache hit)
- Existing CI still passes
- `make dev` still works

### Git workflow

Create branch, commit, push, open PR:
```
git checkout -b chore/turborepo-setup
# ... make changes ...
git add -A && git commit -m "chore: add Turborepo for parallel builds and caching"
git push -u origin HEAD
gh pr create --title "chore: add Turborepo for parallel builds" --body "## Summary
- Add turbo.json with build/dev/lint/type-check/test task definitions
- Update root package.json scripts to use turbo
- Verify all app/package names are consistent

## Test plan
- [ ] pnpm turbo run build succeeds
- [ ] pnpm turbo run build (second run) uses cache
- [ ] pnpm turbo run type-check succeeds
- [ ] CI passes"
gh pr edit $(gh pr list --head chore/turborepo-setup --json number -q '.[0].number') --add-reviewer @copilot
```
```

---

### Session 2: Domain Migration Code Changes

**Copy everything below into Composer:**

```
## Task: Domain Migration Code Changes (P0.2 + P0.7)

Branch: `chore/domain-migration` (create from main)

### Context

We are migrating from filefree.tax to filefree.ai and moving ops subdomains from filefree.tax to paperworklabs.com. The DNS/Vercel/Render dashboard changes are done manually. This PR handles all CODE changes needed.

### Changes required

1. **`apps/filefree/.env.production`** — Update n8n host:
   ```
   NEXT_PUBLIC_API_URL=https://api.filefree.ai
   NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
   N8N_HOST=https://n8n.paperworklabs.com
   ```

2. **`apps/filefree/.env.development`** — Update n8n host:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   N8N_HOST=https://n8n.paperworklabs.com
   ```

3. **`apps/filefree/.env.example`** — Update n8n host reference from `n8n.filefree.ai` to `n8n.paperworklabs.com`

4. **`apps/filefree/src/lib/server-config.ts`** — Update default:
   ```typescript
   N8N_HOST: z.string().default("https://n8n.paperworklabs.com"),
   ```

5. **`apps/filefree/src/app/api/ops/route.ts`** — Update hardcoded URLs:
   - `n8n.filefree.ai` → `n8n.paperworklabs.com` (both healthz URL and dashboard URL)
   - `social.filefree.ai` → `social.paperworklabs.com` (both URL and dashboard URL)
   - ALSO FIX: Line ~190 references old repo `sankalp404/fileFree` — change to `paperwork-labs/paperwork`

6. **`apps/studio/src/lib/command-center.ts`** — Search for any `filefree.tax` or `n8n.filefree.ai` references. Update:
   - `n8n.filefree.ai` → `n8n.paperworklabs.com` if present
   - The `api.filefree.ai` reference is correct, keep it

7. **`infra/env.dev.example`** — Update comments:
   - `n8n.filefree.ai` → `n8n.paperworklabs.com`

8. **`infra/hetzner/compose.yaml`** — Update if any filefree.tax or filefree.ai ops references exist. The n8n and Postiz containers may reference old subdomains.

9. **`apps/filefree/next.config.mjs`** — Add redirect for old domain:
   ```javascript
   const nextConfig = {
     output: "standalone",
     transpilePackages: ["@paperwork-labs/ui"],
     async redirects() {
       return [
         {
           source: "/:path*",
           has: [{ type: "host", value: "filefree.tax" }],
           destination: "https://filefree.ai/:path*",
           permanent: true,
         },
         {
           source: "/:path*",
           has: [{ type: "host", value: "www.filefree.tax" }],
           destination: "https://filefree.ai/:path*",
           permanent: true,
         },
       ];
     },
   };
   ```

10. **Global search**: Search the entire codebase for remaining `filefree.tax` references (excluding `docs/archive/`). Update any found in active code. References in archived docs can stay as historical records.

11. **Global search**: Search for `sankalp404/fileFree` or `sankalp404` anywhere in active code. Update to `paperwork-labs/paperwork`.

### Do NOT change

- `render.yaml` — already has `FRONTEND_URL: https://filefree.ai` (correct)
- `apps/filefree/.env.production` NEXT_PUBLIC_API_URL — already `https://api.filefree.ai` (correct)
- Anything in `docs/archive/` — historical references are fine
- `apis/filefree/app/config.py` FRONTEND_URL default — that's the local dev default, leave as `http://localhost:3000`

### Acceptance criteria

- No active code references `filefree.tax` (except redirect config and archived docs)
- No active code references `n8n.filefree.ai` or `social.filefree.ai`
- No active code references `sankalp404/fileFree`
- n8n URLs point to `n8n.paperworklabs.com`
- Postiz URLs point to `social.paperworklabs.com`
- Old domain redirect is configured in next.config.mjs
- All tests pass

### Git workflow

Create branch, commit, push, open PR:
```
git checkout -b chore/domain-migration
# ... make changes ...
git add -A && git commit -m "chore: migrate filefree.tax → filefree.ai, ops subdomains → paperworklabs.com"
git push -u origin HEAD
gh pr create --title "chore: domain migration filefree.tax → filefree.ai" --body "## Summary
- Update all ops URLs from filefree.tax subdomains to paperworklabs.com
- Add 301 redirect from filefree.tax → filefree.ai in next.config.mjs
- Fix old repo reference (sankalp404/fileFree → paperwork-labs/paperwork)
- Update N8N_HOST across all env files

## Test plan
- [ ] No filefree.tax references in active code (grep)
- [ ] No sankalp404 references in active code (grep)
- [ ] Build succeeds
- [ ] CI passes"
gh pr edit $(gh pr list --head chore/domain-migration --json number -q '.[0].number') --add-reviewer @copilot
```
```

---

### Session 3: Per-Product Theming

**Copy everything below into Composer:**

```
## Task: Wire Per-Product Theming System

Branch: `feat/product-theming` (create from main)

### Context

The brand guide (`.cursor/rules/brand.mdc`) defines 5 distinct color palettes for FileFree, LaunchFree, Distill, Studio, and Trinkets. Currently, `packages/ui/` has a single theme. We need `data-theme` attribute support so all 5 apps share components but look distinct.

### What to build

1. **Create `packages/ui/src/themes.css`** — CSS custom properties for each product theme:

```css
/* FileFree — Violet/Indigo */
[data-theme="filefree"] {
  --primary: 238 76% 57%;
  --primary-foreground: 0 0% 100%;
  --accent-gradient-from: #8B5CF6;
  --accent-gradient-to: #9333EA;
  --brand-bg: 222 84% 3%;
}

/* LaunchFree — Teal/Cyan */
[data-theme="launchfree"] {
  --primary: 173 58% 39%;
  --primary-foreground: 0 0% 100%;
  --accent-gradient-from: #14B8A6;
  --accent-gradient-to: #06B6D4;
  --brand-bg: 220 50% 5%;
}

/* Distill — Deep Blue */
[data-theme="distill"] {
  --primary: 221 83% 53%;
  --primary-foreground: 0 0% 100%;
  --accent-gradient-from: #3B82F6;
  --accent-gradient-to: #1E40AF;
  --brand-bg: 215 28% 11%;
}

/* Studio — Zinc/Neutral */
[data-theme="studio"] {
  --primary: 240 4% 46%;
  --primary-foreground: 0 0% 100%;
  --accent-gradient-from: #71717A;
  --accent-gradient-to: #52525B;
  --brand-bg: 240 10% 4%;
}

/* Trinkets — Amber/Orange */
[data-theme="trinkets"] {
  --primary: 38 92% 50%;
  --primary-foreground: 0 0% 0%;
  --accent-gradient-from: #F59E0B;
  --accent-gradient-to: #EA580C;
  --brand-bg: 20 14% 4%;
}
```

IMPORTANT: These should OVERRIDE the base shadcn theme variables. Check the existing `packages/ui/src/globals.css` (or wherever the base theme CSS is) and make sure the variable names match. The `[data-theme]` selectors should override the `.dark` or `:root` defaults.

2. **Export themes.css from packages/ui**: Add `@import "./themes.css"` in the package's main CSS file, or ensure consuming apps import it.

3. **Update each app's root layout** to add the `data-theme` attribute:

   - `apps/filefree/src/app/layout.tsx`: Add `data-theme="filefree"` to `<body>`
   - `apps/launchfree/src/app/layout.tsx`: Add `data-theme="launchfree"` to `<body>`
   - `apps/distill/src/app/layout.tsx`: Add `data-theme="distill"` to `<body>`
   - `apps/studio/src/app/layout.tsx`: Add `data-theme="studio"` to `<body>`
   - `apps/trinkets/src/app/layout.tsx`: Add `data-theme="trinkets"` to `<body>`

4. **Import themes.css in each app**: Each app's `globals.css` should import the shared themes:
   ```css
   @import "@paperwork-labs/ui/themes.css";
   ```
   Or if the package exports it differently, import from the correct path. Check how `packages/ui` currently exports CSS.

5. **Add a Tailwind utility** for the gradient accent. In each app's globals.css or in the shared package:
   ```css
   .bg-brand-gradient {
     background: linear-gradient(to right, var(--accent-gradient-from), var(--accent-gradient-to));
   }
   ```

6. **Fix GlowCard** in `apps/filefree/src/components/animated/glow-card.tsx`: Replace any hardcoded zinc colors with theme CSS variables (e.g., use `hsl(var(--muted))` instead of hardcoded `zinc-800`).

### Do NOT change

- The actual shadcn component source files in `packages/ui/src/components/` — they already use CSS variables
- FileFree's existing globals.css color definitions — the `[data-theme="filefree"]` overrides layer on top
- Any component behavior or layout

### Acceptance criteria

- Each app renders with its own brand colors when you run `pnpm dev`
- FileFree: violet/purple gradient accent
- LaunchFree: teal/cyan gradient accent
- Distill: deep blue gradient accent
- Studio: zinc/neutral
- Trinkets: amber/orange gradient accent
- GlowCard uses theme variables, not hardcoded colors
- `pnpm turbo run build` succeeds for all 5 apps (or `pnpm run build` if turbo isn't set up yet)

### Git workflow

Create branch, commit, push, open PR:
```
git checkout -b feat/product-theming
# ... make changes ...
git add -A && git commit -m "feat: add per-product theming via data-theme attribute and shared themes.css"
git push -u origin HEAD
gh pr create --title "feat: per-product theming system" --body "## Summary
- Create packages/ui/src/themes.css with 5 product palettes
- Wire data-theme attribute in all 5 app layouts
- Add .bg-brand-gradient utility class
- Fix GlowCard to use theme variables

## Test plan
- [ ] Each app renders with correct brand colors
- [ ] FileFree visual regression: no unexpected color changes
- [ ] Build succeeds for all apps
- [ ] CI passes"
gh pr edit $(gh pr list --head feat/product-theming --json number -q '.[0].number') --add-reviewer @copilot
```
```

---

### Session 4: Hetzner n8n Subdomain Update

**Copy everything below into Composer:**

```
## Task: Update Hetzner n8n/Postiz Configuration for New Subdomains

Branch: `chore/hetzner-subdomain-update` (create from main)

### Context

We're moving n8n from n8n.filefree.ai to n8n.paperworklabs.com, and Postiz from social.filefree.ai to social.paperworklabs.com. This PR updates all Hetzner infrastructure config files.

### Changes required

1. **`infra/hetzner/compose.yaml`** — Update any hostname references:
   - Search for `filefree` in hostnames and update to paperworklabs.com equivalents
   - Ensure n8n `WEBHOOK_URL` (if set) points to `https://n8n.paperworklabs.com`
   - Ensure Postiz `NEXT_PUBLIC_URL` or equivalent points to `https://social.paperworklabs.com`

2. **`infra/hetzner/env.example`** — Update example values to use new subdomains

3. **`infra/hetzner/setup.sh`** — Update any references to old subdomains in Caddy/nginx config or certbot commands

4. **`infra/hetzner/workflows/README.md`** — Update any references to old n8n URLs

5. **`.github/workflows/deploy-n8n.yaml`** — Check if the deploy script references n8n by hostname; update if so

6. **`.github/workflows/infra-health.yaml`** — Check if health checks reference old n8n hostname; update if so

7. **`scripts/deploy-n8n-workflows.sh`** — Update any hardcoded n8n URL references

### Acceptance criteria

- No infra config references `n8n.filefree.ai` or `social.filefree.ai`
- All references point to `n8n.paperworklabs.com` and `social.paperworklabs.com`
- README reflects new URLs
- CI passes

### Git workflow

Create branch, commit, push, open PR:
```
git checkout -b chore/hetzner-subdomain-update
# ... make changes ...
git add -A && git commit -m "chore: update Hetzner config for paperworklabs.com subdomains"
git push -u origin HEAD
gh pr create --title "chore: migrate Hetzner subdomains to paperworklabs.com" --body "## Summary
- Update n8n URLs: n8n.filefree.ai → n8n.paperworklabs.com
- Update Postiz URLs: social.filefree.ai → social.paperworklabs.com
- Update infra config, deploy scripts, health checks

## Test plan
- [ ] No old subdomain references in infra/ directory
- [ ] CI passes
- [ ] After merge + deploy: n8n.paperworklabs.com is accessible"
gh pr edit $(gh pr list --head chore/hetzner-subdomain-update --json number -q '.[0].number') --add-reviewer @copilot
```
```

---

## Phase C: Come Back to Opus For These

These require complex reasoning, security analysis, or architectural design. Do NOT use Composer.

### Session 5: SSN Vision Fallback Fix (CRITICAL SECURITY)

**Why Opus**: This is a security-critical change. The current GPT-4o vision fallback sends the full W-2 image (containing SSN) to OpenAI, violating our #1 security rule. Needs careful design to maintain OCR accuracy while eliminating the SSN leak vector. Options include image redaction using Cloud Vision bounding boxes, region masking, or fallback-to-manual-entry. Opus should evaluate tradeoffs and implement the safest option.

### Session 6: CI Auto-Merge Fix (n8n Workflow Architecture)

**Why Opus**: Requires modifying the n8n agent-thread-handler workflow JSON (complex node graph), designing a pending-merge storage mechanism, creating a new n8n workflow triggered by GitHub check_suite webhooks, and ensuring the merge intent is never lost. Architectural decision-making across GitHub API, n8n workflow design, and Slack UX.

### Session 7: Cost Collector + Studio Agents Dashboard

**Why Opus**: Requires designing an n8n workflow that pulls from the OpenAI Usage API (and eventually Anthropic/Google), writing to Studio's Neon database, then building a Studio dashboard with cost-per-model and cost-per-workflow charts using Recharts. Touches n8n workflow design, database schema, API routes, and React dashboard components. Multiple moving parts that need to work together.

### Session 8: GPT-5.4-mini Model Evaluation

**Why Opus**: Requires understanding model capabilities, running comparison tests, analyzing quality tradeoffs, and making swap decisions that affect all n8n workflows. Strategic reasoning about cost vs quality across the model registry.

---

## Execution Order

```
Phase A (manual, ~1 hour total):
  A.1 Vercel team → A.2 Render workspace → A.3 DNS → A.4 API keys → A.5 Skill → A.6 MCP

Phase B (Composer sessions, ~1-2 hours each):
  Session 1: Turborepo setup
  Session 2: Domain migration code changes
  Session 4: Hetzner subdomain update
  (Sessions 2 + 4 can be merged into one PR if preferred)
  Session 3: Per-product theming

Phase C (Opus sessions, come back for these):
  Session 5: SSN vision fallback fix (CRITICAL — do first)
  Session 6: CI auto-merge
  Session 7: Cost collector + Studio dashboard
  Session 8: Model evaluation
```

Sessions 2 and 4 are related (both domain migration) — you can merge them into one Composer session if you prefer. Session 3 (theming) is independent and can run in parallel.
