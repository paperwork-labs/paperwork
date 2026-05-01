---
last_reviewed: 2026-05-01
---

# Auth Provider Bakeoff — 2026 Q2

**Context:** Vercel-hosted Next.js monorepo; six sub-products (Studio, AxiomFolio-next, FileFree, LaunchFree, Distill, Trinkets) on Clerk via Vercel Marketplace; ~1 week integration sunk; Clerk Hobby (free) with “Powered/Secured by Clerk” on prebuilt UIs; Pro removes branding at **$25/mo** ($240/yr on annual) per [Clerk pricing](https://clerk.com/pricing). Vercel’s own auth skill still positions **Clerk** as the default for fastest Vercel setup and **Auth0** for deep enterprise identity ([Vercel auth skill, local cache](https://vercel.com)).
**Scope:** Research synthesis (Apr 2026). Not legal advice; verify ToS for any “hide the footer with CSS” workaround.

## TL;DR (3 sentences max)

**Stay on Clerk for now**, ship the embedded-UI + appearance approach or budget **$20–25/mo** to remove branding when it stops being a rounding error—your aggregate cost to migrate *six* apps off Clerk while you still have ~zero MAU is not “one week” but **2–4+ engineer-weeks of coordinated churn plus user/session/OAuth re-plumbing** unless you accept new lock-in. **If you are allergic to any hosted branding or want zero recurring auth line-item**, the strongest open stack for *new* greenfield work in 2026 is **Better Auth** (or **Stack Auth** if you want a Clerk-like hosted layer without Clerk’s Hobby branding rules—but watch MAU/SSO tier gates), not a fresh bet on long-term *feature* velocity in **Auth.js** alone. **For Distill’s enterprise SAML/OIDC**, plan **Clerk Pro/Business/Enterprise connections** *or* add **WorkOS**-style per-connection pricing when the first paid SSO customer is on paper—not Auth0 at startup scale unless you must.

## Scoring matrix

Scale **1–5** (5 = best on that axis). “**Migration**” = ease of *leaving* Clerk now (5 = no move; 1 = heaviest lift). “**Lock-in**” = ease of *exit* later (5 = low lock-in / portable design). “**B2B SSO**” = SAML/OIDC for customer IdPs *without* absurd minimums. Totals are **out of 45** (9 columns).

| Provider | Branding | DX | Cost | Lock-in | Multi-tenant | B2B SSO | Self-host | Maturity | Migration | **Total** |
|----------|----------|----|----|---------|-------------|---------|----------|----------|-------------|-----------|
| **Clerk** (baseline) | 2 | 5 | 4 | 2 | 4 | 3 | 1 | 5 | 5 | **31** |
| **Auth.js / NextAuth v5** | 5 | 4 | 5 | 4 | 3 | 2 | 5 | 4* | 2 | **34** |
| **Stack Auth** | 4 | 4 | 3 | 3 | 4 | 2 | 4** | 3 | 2 | **29** |
| **Supabase Auth** | 5† | 4 | 3‡ | 3 | 3 | 2§ | 2 | 5 | 2 | **29** |
| **Lucia** | 5 | 3 | 5 | 5 | 2 | 1 | 5 | 4 | 1 | **31** |
| **Better Auth** | 5 | 4 | 5 | 4 | 3 | 2¶ | 5 | 4 | 2 | **35** |
| **WorkOS** (AuthKit + SSO) | 4 | 3 | 3 | 2 | 4 | 5 | 1 | 5 | 2 | **30** |
| **Auth0** | 3 | 3 | 1 | 2 | 4 | 4** | 1 | 5 | 2 | **25** |
| **Cognito** | 5 | 1 | 3 | 2 | 2 | 3 | 0 | 4 | 1 | **21** |
| **Stytch** | 3 | 4 | 3 | 2 | 4 | 3** | 1 | 4 | 2 | **28** |

\*Auth.js: maintainers (Better Auth) recommend **new** projects use Better Auth; v5 = security/urgent fixes, not aggressive feature roadmaps ([Better Auth, Sep 2025](https://www.better-auth.com/blog/authjs-joins-better-auth), [Auth.js v5 release/migration](https://authjs.dev/getting-started/migrating-to-v5?authentication-method=middleware)). **Stack Auth** self-host is strong; **hosted** “custom branding / OIDC / SAML” is paid (Team $49, Growth $299) per [Stack pricing](https://stack-auth.com/pricing) as of 2026. †No third-party “Supabase” logo on *your* UI; auth is your DB + their infra. ‡Tied to Supabase project/egress/MAU org caps ([Supabase usage docs](https://supabase.com/docs/guides/platform/billing-on-supabase)). §SSO/SCIM for **SSO users** and quotas is a paid/Team concern per Supabase’s billing table—don’t use Free for serious SAML without reading current docs. ¶B2B/SSO via plugins/enterprise infra tier ([Better Auth pricing](https://www.better-auth.com/pricing)): **$299/mo Business** product lists self-service SSO (verify feature list at ship time). **Stytch** email branding: pay to remove per third-party writeups; free tier 10K MAU + 5 SSO/SCIM connections on [Stytch pricing](https://stytch.com/pricing) / [changelog Nov 2024](https://changelog.stytch.com/announcements/2024-11-22-updated-self-serve-pricing).

**How Vercel frames it (first-party):** The shipped **auth** skill’s decision matrix: fastest on Vercel + prebuilt UI → **Clerk**; enterprise / SAML / multi-tenant depth → **Auth0**; passwordless/flow builder → **Descope** (not in your ten-candidate list but relevant peer). ([Vercel Marketplace integrations](https://vercel.com/docs/integrations))

## Key questions (short answers)

### 1) Is “Powered by Clerk” a deal-breaker?

**No for most startups—treat it as a product/branding** decision: Pro at **$25/mo** buys official removal and other knobs ([Clerk pricing](https://clerk.com/pricing)). A **CSS / embedded-UI** workaround is likely **annoyance + ToS/compliance** risk: Hobby explicitly ties branding to prebuilt UIs; hiding it may be against terms even if enforcement is rare. If the founder cannot tolerate *either* cost *or* ambiguity, that pushes toward **self-hosted/fully-owned UI** (Better Auth, Lucia, or Stack self-host), not a different SaaS with another logo (Stytch still sells **email branding** removal on paid per third-party summaries—verify [Stytch](https://stytch.com/pricing)).

### 2) Cost of switching later vs now

**Now:** mostly **6× app surface area** (middleware, env, `ClerkProvider`, sign-in routes, `auth()` call sites) + Marketplace wiring—bounded but duplicated. **Later:** *plus* user migration, session invalidation, OAuth app secrets rotation, any org/roles data, support burden, and **calendar coordination**. Rule of thumb: switching cost **grows with MAU and product complexity superlinearly**; at ~0 MAU, *calendar* and *focus* dominate more than data migration, but you still should not trivialize **six** deployables.

### 3) Who beats Clerk on Branding + DX + free-tier ceiling (6 Vercel apps)?

- **Branding (no paywall):** open libraries (**Better Auth**, **Lucia**, **Auth.js**) or **self-host Stack/Supabase**.  
- **DX + time-to-ship for many Next apps:** **Clerk** still leads among hosted drop-ins (matches Vercel’s own matrix).  
- **Free auth MAU headroom (hosted):** **Clerk Hobby ~50K MRU** (retained user definition on Hobby—see [Clerk pricing](https://clerk.com/pricing)); **WorkOS AuthKit 1M MAU** free, **SSO connections** are the cost driver at **~$125/connection** tier (see [WorkOS pricing](https://workos.com/pricing)); **Stytch 10K MAU** free; **Stack free** 10K users per marketing/pricing page ([Stack](https://stack-auth.com/pricing)). **There is no single “beats Clerk everywhere”**—it’s a three-way trade (branding, DX, hosted limits).

### 4) Is Auth.js v5 “production-ready enough” to bet the company?

**To run in production: yes, many teams do**—mature core patterns and App Router `auth()`. **To bet the *next five years* of feature velocity* on v5 alone: the maintainers’ own 2025–2026 story is “Better Auth is the home; Auth.js gets security/urgent fixes; new work → Better Auth.”** ([announcement](https://www.better-auth.com/blog/authjs-joins-better-auth), [discussion #13252](https://github.com/nextauthjs/next-auth/discussions/13252)) So for **new** greenfield in this repo, **frame the real fork as Better Auth vs Clerk**, not v5 vs Clerk.

### 5) What’s the Stack Auth story (Apr 2026)?

- **Positioning:** Open-source (MIT/AGPL), “Auth0/Clerk alternative,” optional hosted, export/self-host narrative ([GitHub `stack-auth/stack-auth`](https://github.com/stack-auth/stack-auth)).  
- **Signals:** **~6.7k+ stars**, active 2026 commits, moderate issue count—**not abandoned**, not yet “Clerk-level everywhere mindshare.”  
- **Economics vs you:** **Free: 10K users**; **Team $49** adds custom branding and OIDC/OAuth SSO; **Growth $299** for SAML count ([Stack pricing](https://stack-auth.com/pricing)). Contrast: **Clerk** gives **higher** free MAU for hosted but **worse** official branding on Hobby.  
- **Risk:** Smaller org than Clerk/WorkOS; enterprise procurement may ask more questions; **B2B SAML** is explicitly a **paid** tier.

## Decision options (3–4)

### Option 1: Stay with Clerk + free workaround (PR #210) or pay Pro for branding

- **Pros:** Sunk Vercel Marketplace fit; best-in-class **Next** DX; 50K MRU on Hobby; **B2B SAML/OIDC** available on Pro (1 enterprise connection included, more priced—see [Clerk pricing / omnibus writeups](https://clerk.com/pricing), [authomnibus](https://authomnibus.com/vendors/clerk/)) when Distill needs it.  
- **Cons:** **Hobby branding**; DNS/satellite/Account Portal product complexity; **vendor JWT/users** in Clerk.  
- **Risk:** **ToS/brand** risk if you hide prebuilt footers; low *observed* public enforcement, but not zero. Pro removes that class of issue for **$25/mo** ([Clerk](https://clerk.com/pricing)).  
- **Migration cost from here:** **$0** + ongoing mental overhead.

### Option 2: Switch six apps to **Better Auth** (or Auth.js v5 *only* if you accept maintenance-mode trajectory)

- **Pros:** **No** vendor branding; **no** per-user fee for the OSS framework; **your DB** = sessions, portability; first-class 2026 momentum ([Better Auth](https://www.better-auth.com/), [blog on Auth.js](https://www.better-auth.com/blog/authjs-joins-better-auth)). Optional [Better Auth Cloud / Infrastructure](https://www.better-auth.com/pricing) for dashboard/audit.  
- **Cons:** You own **security, abuse, email deliverability, upgrades** for six surfaces; B2B SAML is **work** (plugin/enterprise add-ons) vs Clerk’s productized dashboard. **Multi-app monorepo** = copy patterns + shared package discipline.  
- **Migration cost:** **~2–4+ engineer-weeks** to move all six + test matrix + cutover; higher if you need data migration/parallel runs.

### Option 3: **Stack Auth** (hosted) or self-host

- **Pros:** “Clerk-shaped” with OSS escape hatch; public testimonials claim fast Clerk → Stack migration ([Stack site](https://stack-auth.com/)). **Branding** on free is **better than Clerk’s Hobby** for many teams (no “Powered by Stack” in the same *mandatory* prebuilt-UI way—verify live UI in staging).  
- **Cons:** **10K** free user ceiling vs **Clerk 50K**; SAML/OIDC gating to **$49–$299** ([Stack](https://stack-auth.com/pricing)). Smaller vendor.

### Option 4: **WorkOS**-forward for Distill; Clerk elsewhere (hybrid) — *only* if you accept two identity systems

- **Pros:** **1M MAU** free for AuthKit; **SSO** priced **per customer connection**—fits **B2B** when each enterprise is one “connection” ([WorkOS](https://workos.com/pricing)).  
- **Cons:** **Operational complexity** (two products, two bills, cross-app SSO story is hard); you probably **don’t** want this at six consumer-ish surfaces *unless* Distill is decoupled early.

### (Brief) also-rans in this map

- **Stytch:** Strong **B2B + passwordless**; 10K MAU free, 5 SSO connections free; email branding can be a future cost—evaluate if Distill is passwordless-first ([Stytch](https://stytch.com/pricing)).  
- **Auth0 / Cognito:** Auth0: **$0–25K MAU free** with 1 enterprise connection on Free **B2B** narrative ([Auth0 blog 2024](https://auth0.com/blog/auth0-b2b-plans-upgraded/)) but paid tiers ramp fast; overall **$$$ and complexity** vs Clerk for your stage. Cognito: **cheap at scale, poor DX**—only if the rest of the stack is AWS-rigid.  
- **Supabase Auth:** **50K MAU** free, **$25** Pro is familiar, but you adopt **data + pause rules + org limits**; SAML/SSO “MAU for SSO” is *not* the same as Clerk’s B2B story—re-read [Supabase billing](https://supabase.com/docs/guides/platform/billing-on-supabase) before betting Distill.  
- **Lucia:** Excellent **code-first** sessions; you still build or buy **IdP, email, org UI** for six products—**high control, high build**.

## Recommendation

**Default: stay on Clerk**—Vercel’s first-party material still steers to Clerk for speed, your integration is *fresh* but **not cheap** to replicate six times, and **$25/mo** to remove branding is *smaller* than a migration burn unless branding is a **values/legal** issue, not a **$300** issue. If you *reject* that trade on principle, **do not** fall back to Auth.js *greenfield*; pilot **Better Auth** in *one* low-risk app, extract a shared `@paperwork/auth` package, then roll—**after** you’ve written a one-page “Distill IDP” requirement (SAML? SCIM? how many customer connections in year one?). If Distill is **enterprise-SSO-first**, pair Clerk Pro/Business (connections) **or** evaluate **WorkOS** for Distill *only*—not as a panacea for the whole 6-app portfolio on day one.

## If we switch: migration plan (rough)

1. **0.5 wk** — Decisions: target stack (Better Auth vs Stack), Distill B2B requirements, parallel-run strategy (per-tenant feature flag).  
2. **1 wk** — Shared library: middleware patterns, `auth()`-equivalent, session type, E2E auth smoke for one “golden” app.  
3. **1.5–2.5 wk** — Port remaining five apps, env + Vercel + OAuth consoles, cutover playbooks, rollback.  
4. **0.5–1 wk** — User comms, session invalidation, support monitoring.  
5. **Ongoing** — Security patch cadence, abuse/rate limits, IDP test matrix (esp. B2B).

**Total (order of magnitude): 3–6 engineer-weeks** for six apps, assuming no exotic org migrations—**more** if you must migrate user passwords/social without downtime.

## Sources (core)

- [Clerk pricing](https://clerk.com/pricing)  
- [Vercel Marketplace integrations](https://vercel.com/docs/integrations)
- [Better Auth: Auth.js joins Better Auth, Sep 2025](https://www.better-auth.com/blog/authjs-joins-better-auth)  
- [Auth.js migrating to v5](https://authjs.dev/getting-started/migrating-to-v5?authentication-method=middleware)  
- [Stack Auth pricing](https://stack-auth.com/pricing) · [GitHub](https://github.com/stack-auth/stack-auth)  
- [WorkOS pricing](https://workos.com/pricing)  
- [Stytch pricing](https://stytch.com/pricing) · [Stytch self-serve update Nov 2024](https://changelog.stytch.com/announcements/2024-11-22-updated-self-serve-pricing)  
- [Supabase billing / MAU / SSO](https://supabase.com/docs/guides/platform/billing-on-supabase)  
- [Auth0 B2B free upgrades blog](https://auth0.com/blog/auth0-b2b-plans-upgraded/)  
- [Better Auth products/pricing](https://www.better-auth.com/pricing)  

---
*File generated for Paperwork Labs — AUTH_PROVIDER_BAKEOFF — 2026-04-26*
