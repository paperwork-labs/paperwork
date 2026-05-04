---
last_reviewed: 2026-05-03
doc_kind: strategy
domain: brain
status: draft
audience: founder
authored_by: opus-orchestrator (read-only audit, single Opus session)
---

# Brain as Company OS as a Service — Strategic + Architectural Audit

> **Status:** Draft, single-session audit. Not a commitment. **Founder lock (2026-05-03): internal-first, with a B2B-ready spine** — ship the company OS for Paperwork Labs; defer public productization; keep the platform shaped so a second `organization_id` (or a design partner) is weeks of wiring, not a rewrite. §§1–7 follow that lock.
>
> **Companion docs:**
> - [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md) — the bible (**D1–D76**; D64–D76 Company OS + Studio surface doctrine added **2026-05-03**). **PR [#664](https://github.com/paperwork-labs/paperwork/pull/664)** (merged) already codified Reference Data Storage, Brain Gateway (`POST /v1/brain/invoke`), and MCP-pointer IP skills; do not duplicate that material here.
> - [`docs/audits/BRAIN_BIBLE_GAP_AUDIT_2026-05-03.md`](../audits/BRAIN_BIBLE_GAP_AUDIT_2026-05-03.md) — the architecture-side gap audit that named D64–D76 as missing
> - [`docs/audits/wave-1/*.md`](../audits/wave-1/) — five concrete code audits (conversations, briefings, secrets, agent dispatch, people/sprints/epics) showing what's actually wired vs claimed
> - [Locked plan: Brain = Curated Multi-Tenant Agent OS](file:///Users/paperworklabs/.cursor/plans/brain_=_curated_multi-tenant_agent_os_—_final_plan_4c44cfe9.plan.md) — the existing engineering plan that already commits to multi-tenant RLS + skill registry + invocation gateway
>
> **What this audit explicitly is and isn't.** This is a strategy doc. **Bible patches** for D64–D76 and §8 Studio are **landed in** [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md) (2026-05-03); §7 below points to those sections instead of duplicating patch text. It is **not**: a PRD, a customer interview synthesis, an Olga workshop, a financial model, or a security review. See §8 (honest scope footer) for the full list of what's NOT covered.

---

## Table of contents

- [§0 — Should we even productize this? (Decision memo)](#0--should-we-even-productize-this-decision-memo)
- [§1 — Vision lock](#1--vision-lock-only-if-0-lands-on-productize-or-design-partner)
- [§2 — The tool-category audit (the core)](#2--the-tool-category-audit-the-core)
- [§3 — Multi-tenancy reality check](#3--multi-tenancy-reality-check)
- [§4 — Studio as the licensable UI](#4--studio-as-the-licensable-ui)
- [§5 — What lands FIRST before licensing is even possible](#5--what-lands-first-before-licensing-is-even-possible)
- [§6 — Risk + competitive positioning](#6--risk--competitive-positioning)
- [§7 — Bible patches (copy-paste-ready)](#7--bible-patches-copy-paste-ready)
- [§8 — Honest scope footer + open questions](#8--honest-scope-footer--open-questions)

---

## §0 — Should we even productize this? (Decision memo)

**You explicitly asked me to start here.** Quoting your reply to Q7 of the strategic clarifiers verbatim:

> *"you tell me.. do we [have a moat]? or we just tame it to building for us — i feel us only vs multi tenant not that difficult"*

That sentence is the entire reason §0 exists. The rest of this doc is downstream of the answer.

### §0.0 — Founder lock (2026-05-03): internal-first + easy B2B optionality

You chose: **focus on internal-only**, but keep **easyish** paths to B2B later.

That is **not** "don't build multi-tenancy." It *is* "don't build **customer SaaS** yet" — no public landing page, no Stripe-first roadmap, no SOC 2 theater as a gating project — while you **do** build the **same platform bones** the locked plan already needs (single source of truth, gateway, real tenant boundary, no split-brain ops graph). Those bones are what make B2B a **small increment** later (new org row + auth + RLS flags + billing wire-up) instead of a **replatform** because you dogfooded on `goals.json` + SQLite FTS forever.

**Yes, you still need to build it** — for three independent reasons that all point at the same work:

1. **Internal honesty** — Wave 1 audits show split-brain (Postgres mirror vs filesystem/SQLite canonical; goals in three places; dispatch not wired). Internal-only on broken substrate is just slower confusion, not a moat.
2. **Consumer Brain** — D12/D49 and the final plan assume org-scoped memory + skills; that is the same `organization_id` discipline as B2B.
3. **Future B2B** — if tenancy + gateway + vault never land, "flip to B2B" is a lie: you'd be selling a second product you never ran.

**What you deliberately *don't* build on the internal-first path** (until there is a paying customer or a signed design partner):

| Defer (revenue / GTM surface) | Still build (platform spine) |
|---|---|
| Public marketing site, pricing page, sales deck | `organization_id` correctness everywhere queries touch; no cross-tenant reads |
| Stripe Checkout, metered billing, dunning | Usage-meter schema + hooks when gateway exists (can accrue $0 internally) |
| SOC 2 project, DPA library, customer trust center | RLS or equivalent fail-closed pattern for shared DB; audit log already partially there |
| White-label polish (custom domains, full theme studio) | `features_enabled` / plan JSON on `agent_organizations` (already in schema) — ship with one internal theme first |
| Multi-tenant Clerk org signup + invite emails | Admin-token path to provision a *second* org in staging / for a friend without public self-serve |

**The "easy B2B" definition:** after the spine is done, adding an external tenant is **days** (org + API keys + RLS verification + a billing stub), not **quarters** (rebuilding the ops graph from JSON files).

### §0.1 — The three options on the table

There are **three honest paths**, not "yes/no productize." The doc treats each as a real option with a falsifiable trigger that flips it on or off.

| Option | What it means in 90 days | What it means in 365 days | Founder cost / month | Reversible? |
|---|---|---|---|---|
| **A — Stay internal forever** | Brain serves Sankalp + Olga only. Wave 1 audits get fixed, gateway lands, IP MCP servers ship, Studio gets coherent. Zero customer surface. | Brain is the deepest dogfood in any company in the venture. We build with it, not sell it. We sell **outputs from it** (FileFree, LaunchFree, Distill APIs, AxiomFolio) but never the OS itself. | 0 (no incremental cost over current build) | Trivially. Door stays open. |
| **B — Internal + design partner (covert beta)** | Stay internal, but turn on the multi-tenancy primitive (RLS + tenant isolation) in service of Wave B of the locked plan. Quietly invite **3 hand-picked 1–3p shops** (founder friends — no SLAs, no billing, no support promises). | Either: (i) "they all stopped using it after 30 days, kill it" or (ii) "two of them won't stop using it, plus they want to pay" → flip to C. | ~$30–60/mo extra Neon + Render headroom + email | Yes, painful. Requires unwinding 3 design partners and the multi-tenant assumption (but multi-tenancy serves Consumer Brain too, so the work isn't wasted). |
| **C — Productize now** | Public landing page, billing, SOC 2 plan, 5+ first paying customers in 90 days. Customer success becomes a real persona Sankalp wears 5–10 hrs/week. | $5–50K MRR or "we shipped a SaaS that 4 people pay for and it consumes 60% of our attention" | $300–800/mo (Stripe billing + status page + Linear + a customer-support inbox + SOC-2 readiness vendor) + 10–20 hrs/week founder time | Hard. Refunds, contracts, public deprecation post. |

**Original recommendation in first draft: B (Internal + Design Partner) for 90 days.** With your §0.0 lock, the operating mode is **A+** — internal-first + B2B-ready spine — with **optional B** (3 quiet design partners) only if you want market signal without productizing; **not required** to validate the spine. Reasoning in §0.5. The rest of §0 is the data that still matters (competitive pressure + moat honesty + plumbing cost).

### §0.2 — The market reality (the McKinsey-style bit you asked for)

Five honest observations from the live data, not from training-data vibes (sources cited inline, all retrieved 2026-05-03 — current as of "today" in this audit):

**1. The TAM is real, but mostly already absorbed.** "Agentic AI Enterprise Platform" market is $4.35B in 2025 → projected $47.8B by 2030 at 61% CAGR ([source](https://marqstats.com/reports/agentic-ai-enterprise-platform-market/)). But: **the top four players (Microsoft Copilot Studio, AWS Bedrock Agents, Google Cloud agents, LangChain) hold ~48% of global revenue today** ([AgentMarketCap Q2 2026 commoditization report](https://agentmarketcap.ai/blog/2026/04/13/ai-agent-stack-commoditization-clock-q2-2026)) and have all the distribution. Salesforce Agentforce ate the CRM-adjacent agent space. The orchestration layer is **commoditizing as we speak** — at least 14 agent-framework startup acquisitions late 2024 → early 2026, classic consolidation signal.

**2. The "AI in your existing tool" play is already free or nearly free.** Three concrete numbers worth memorizing before pricing anything:

| Incumbent | What it bundles | Effective marginal price | Threat to Brain-as-OS |
|---|---|---|---|
| **Atlassian Rovo** | Search, chat, agents, Studio across Jira/Confluence/JSM | **$0** (included in Standard/Premium/Enterprise of any Atlassian Cloud product, with 25/70/150 credits/user/mo respectively, [pricing](https://www.atlassian.com/software/rovo/pricing)) | **Existential** for any team already paying Atlassian. We cannot beat free. |
| **Notion Custom Agents** | Workspace-wide agents, Connectors to Slack/Drive/etc. | $10/1,000 credits on Business/Enterprise (which are $10–18/user/mo); free in beta through May 2026, [help center](https://www.notion.so/help/custom-agent-pricing) | **High** for any team using Notion as their wiki. The only thing they don't do is cross-tool DO at the level Lindy does. |
| **Microsoft 365 Copilot** | Agents across Word/Excel/Outlook/Teams via Copilot Studio | $30/user/mo (or bundled in M365 E5 expansions) | **High** in Microsoft shops. Doesn't matter for Google-Workspace shops (which is most of our target) but rules out half the SMB market. |
| **Glean** | Cross-tool search + chat + agents | ~$45–50/user/mo + Flex credits, custom enterprise pricing ([source](https://www.getmetronome.com/pricing-index/glean)). $200M ARR Jan 2026, $7.2B valuation Feb 2026 ([source](https://www.glean.com/blog/glean-200m-arr-milestone)) | **Medium** — they own enterprise (200+ employees). They DON'T compete in 1–20p shops on price or sales motion. |
| **Lindy** | Agent-only, no memory layer | $50–200/mo flat, no per-seat ([pricing](https://www.lindy.ai/pricing)) | **Medium** — pure DO play. They have no memory or cross-tool query layer. Brain's verb pair (REMEMBER + DO) is genuinely differentiated here. |
| **Relevance AI** | Agents + light memory | $19–234/mo ([pricing](https://relevance.ai/pricing)) | **Medium** — same shape as Lindy but cheaper entry. |

**The brutal read:** if a customer already pays Atlassian, Notion, or Microsoft, *the agent layer is becoming free or near-free as a bundled feature*. Brain-as-OS only exists in the wedge where the customer **does NOT have a single dominant SaaS to bundle agents from** — i.e., the SaaS-sprawl shop running 6–10 small tools, none of which is bundle-worthy. That maps to your wedge choice (a + b + d), with **(d) 1–10p teams being the strongest** because they're least likely to be locked into a single Atlassian/Notion/Microsoft seat.

**3. Adoption is still pilot-heavy, even at the F500 level.** Per the same TAM reports: **only ~2% of enterprises had deployed agentic AI at scale by end of 2025; 45% of F500 are piloting** ([Marqstats](https://marqstats.com/reports/agentic-ai-enterprise-platform-market/)). Translation: the buyers are not yet sophisticated enough to evaluate one platform vs another on technical merits. This is good (we have time) AND bad (we can't differentiate on technical depth because nobody's measuring it yet).

**4. SMB-tier agent platforms (Lindy, Relevance, Cognosys, MultiOn) are alive but small.** Public ARR numbers don't exist; reasonable inference from team size + funding rounds is each is in the **$5–50M ARR band** after 2–3 years of operation. Lindy's flat-rate $50–200/mo SMB pricing tells you the segment exists but doesn't pay much per logo. **A 1,000-customer SMB SaaS at $100/mo blended ARPU = $1.2M ARR.** That's the realistic order-of-magnitude prize for the "1–10p team OS" wedge in years 1–2.

**5. The cross-tool memory + DO combination is not yet won.** Glean is read-only at heart (search + summarize). Lindy is DO-only (no persistent cross-tool memory). Notion AI is single-tool. Atlassian Rovo is single-ecosystem. **The "REMEMBER + DO across the whole company" position is genuinely open** — but it's open because (a) it's hard to ship, (b) the buyers aren't asking for it yet (only 2% scaled), and (c) the bundled incumbents are racing toward it in ways that erode the position monthly.

### §0.3 — The honest moat audit

You asked: *"do we [have a moat]?"* Bible-claimed moats vs reality, line by line:

| Claimed moat | Bible reference | Reality (2026-05-03) | Verdict |
|---|---|---|---|
| **Memory Moat** (D49) — accumulated context per company is the switching cost | [`BRAIN_ARCHITECTURE.md` §1 D49](../BRAIN_ARCHITECTURE.md) | True FOR US (Sankalp + Olga + 18 months of repo + decisions + episodes). For a **new customer on day 1**, the moat is **zero** — they don't have years of memory yet. The moat ACCRUES TO US as we ingest customer data; the *customer* doesn't feel it for 6–12 months. Atlassian + Notion already have years of customer wiki/ticket data; that's their memory moat. | **REAL FOR US, FUTURE FOR CUSTOMERS** — does not protect against a price war in years 1–2 |
| **Cheap-agent fleet doctrine** | [`.cursor/rules/cheap-agent-fleet.mdc`](../../.cursor/rules/cheap-agent-fleet.mdc), [`apis/brain/data/agent_dispatch_log.json`](../../apis/brain/data/agent_dispatch_log.json), [`docs/PR_TSHIRT_SIZING.md`](../PR_TSHIRT_SIZING.md) | Real, operationally valuable, validated in 2 sprints. **But invisible to the customer.** It's our COGS advantage, not a feature they pay for. Lindy / Relevance / Sierra all have similar dispatchers; ours is just built around the merge queue + procedural memory pattern, which is unique but copyable. | **REAL COGS ADVANTAGE, NOT A CUSTOMER-FACING MOAT** |
| **MCP-per-product** (D62 + locked plan) | [`apis/axiomfolio/app/mcp/server.py`](../../apis/axiomfolio/app/mcp/server.py) (built); FileFree + LaunchFree MCP TODO Wave I3 | Architectural bet, not a moat. **The Brain Gateway (`POST /v1/brain/invoke`) doesn't exist yet** — Wave C is pending in the locked plan. AxiomFolio MCP is built but Brain doesn't yet consume it through the gateway. The "every tool is an MCP server" thesis is right; it's also rapidly becoming the industry default (Anthropic, OpenAI, Microsoft all converging on MCP). | **WILL BECOME TABLE STAKES, NOT A MOAT** |
| **Studio as the company OS surface** | [`apps/studio/src/app/admin/`](../../apps/studio/src/app/admin/) — 44 admin pages today | Real surface area exists. **But:** Wave 1 audits show extensive split-brain (JSON files alongside DB tables for goals, workstreams, conversations, dispatch logs), unmounted UI components (`SprintsOverviewTab`), redirects to non-existent tabs (`/admin/sprints`), and Conversations storing canonical data on filesystem + SQLite FTS5 with Postgres as a *mirror* (not the other way around). | **REAL UNDER CONSTRUCTION; CURRENTLY NOT A MOAT — IT'S TECH DEBT** |
| **Founder dogfood** | Sankalp + Olga as canaries (D54, audit-proposed D72 "Founder Dogfood Mode") | Real for Sankalp, **not yet for Olga** (per audit: she's onboarding to Conversations as her primary surface). You said in Q6: *"Olga is invisible till we make money, she is never the bottleneck."* Translated: dogfood is single-founder dogfood, with all the usual risks (one taste, no consensus). | **REAL CREDIBILITY, NARROW** — better than zero, weaker than "two-founder dogfood" |
| **Cross-product knowledge graph** (F125) — tax + LLC + portfolio + brokerage + Brain ops | Bible §11 + §14 | **Architecturally true, operationally absent.** The cross-product graph requires FileFree, LaunchFree, AxiomFolio, and Distill all to be live AND for Brain to query their MCP servers AND for the entity-resolution layer to merge across them. Today: AxiomFolio has the MCP, FileFree+LaunchFree don't, Distill doesn't exist as a code surface yet. Cross-product graph is a **2027 thing, not a 2026 thing**. | **REAL, BUT LATE** |

**Net moat audit:** the moat is a **2028 picture being sold as a 2026 picture**. Today's real moat is "we built it and others didn't (yet)" — which works against slow incumbents (Drake/Lacerte for tax) but **does not work against Atlassian/Notion/Microsoft/Glean** who are all shipping monthly.

### §0.4 — How hard is multi-tenant *really*?

You said: *"i feel us only vs multi tenant not that difficult."* Let's stress-test that with code-level facts before you commit.

**The good news.** The data model already assumes multi-tenancy. Every multi-tenant table has `organization_id TEXT NOT NULL` ([D12 in bible](../BRAIN_ARCHITECTURE.md#d12-full-multi-tenant-backend), enforced at schema level in [`apis/brain/alembic/versions/001_initial_schema.py`](../../apis/brain/alembic/versions/001_initial_schema.py)). The `parent_organization_id` pointer for the platform-org hierarchy is in place ([`apis/brain/app/models/organization.py:15`](../../apis/brain/app/models/organization.py)). The locked plan's Wave B is exactly this work and was already scoped before today.

**The bad news, unflinching.** Each line below is a real gap in the codebase as of today:

1. **No RLS in the schema today.** All `organization_id` enforcement is **app-layer only**. A single SQLAlchemy query that forgets `.where(Episode.organization_id == ctx.org_id)` leaks one customer's data to another. The locked plan's Wave B says "RLS migration" — that's 3+ days of careful work + a 24-hour staging burn-in + ~30 distinct queries to retrofit, per the rate-limit / audit audits.
2. **The Brain Gateway implementation must match the bible spec.** The invocation contract is documented in [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md) (merged doctrine from [PR #664](https://github.com/paperwork-labs/paperwork/pull/664)). The **runtime** `POST /v1/brain/invoke` path is still Wave C delivery work — a `grep` over `apis/brain` for the dispatcher may still be thin until that wave ships. Multi-tenant enforcement stays incomplete until code matches the spec everywhere skills are called.
3. **`brain_user_vault` exists in the schema but is unused code.** [Wave-1 secrets audit](../audits/wave-1/secrets-vault.md) says: no read path, no write path, no API. For multi-tenant, every customer's per-user OAuth tokens (Gmail, Plaid, etc.) need a vault. We have the table, no plumbing.
4. **Dispatch log + outcomes are split-brain.** [Wave-1 agent-dispatch audit](../audits/wave-1/agent-dispatch.md): `agent_dispatches` table (mig 014) exists, but Cursor `Task` dispatches do NOT auto-persist there. `autopilot_dispatcher.install()` is **never called**, so the 5-min loop doesn't run. Migration 014 backfill targets the wrong JSON path. Multi-tenant dispatch observability requires this to be coherent FIRST.
5. **Goals, workstreams, conversations have split-brain persistence.** [Wave-1 people-sprints-epics](../audits/wave-1/people-sprints-epics.md): `/admin/goals` reads `goals.json`, but a separate SQL `goals` table exists, AND `OBJECTIVES.yaml` is a third source. None unified. Multi-tenant means each customer needs ONE source per concept; can't ship with three.
6. **Studio has 44 admin pages, ~30% have inconsistent data sources.** Same audit. Customers can't get a coherent product if internal pages disagree with each other.
7. **No per-tenant rate limiting.** [`apis/filefree/app/rate_limit.py`](../../apis/filefree/app/rate_limit.py) (now Wave K8) limits per-IP / per-user. Per-tenant is a future story.
8. **No billing surface.** Stripe stub deferred per locked plan. No usage meter rows accruing. No customer-facing invoice. No suspension flow when a tenant exceeds quota.
9. **No customer onboarding flow.** Studio assumes you ARE the founder. "Sign up, name your org, invite teammates, install your first skill" doesn't exist as a flow. Clerk auth exists but is wired for paperwork-labs employees, not external orgs.
10. **No SOC-2 footing.** Customer data on Neon means we should at minimum: (a) DPA template, (b) sub-processor list, (c) data-deletion API endpoint, (d) per-tenant data residency choice if any customer asks. None exist as documented surfaces.

**Honest size estimate**, knowing this codebase: turning the 10 items above into "could ship to a paying customer" is **~6–10 weeks of focused work, not 1–2 weeks**. Items 1–4 are the hard ones (RLS retrofit + gateway + vault wiring + dispatch coherence); items 5–10 are mostly mechanical. *None* of them are individually "research" items — they're all known problems with known solutions. But 6–10 weeks is meaningfully different from "not that difficult." It's also 6–10 weeks where Sankalp is NOT working on Consumer Brain, AxiomFolio, FileFree EFIN, or any other revenue-bearing work.

Your instinct that it's "not that difficult" is *almost* right — the **architecture** isn't difficult (the bible is correctly designed for multi-tenancy from the start). The **plumbing** is what takes the time, and the plumbing isn't optional.

### §0.5 — Recommendation (updated for §0.0): spine first, partners optional, productize last

**Why not "pure A" (internal forever with zero multi-tenant work):** the multi-tenancy + gateway + split-brain fixes in the locked plan are **already justified internally** — Consumer Brain (D49), coherent Studio, and the Wave 1 audit findings. Skipping them to "stay simple" actually makes the system *harder* to operate, not easier.

**Why B (design partners) is optional under §0.0:** you can run **A+** (internal + spine) without 3 external orgs if founder time is the constraint. Design partners are still the cheapest way to falsify "would anyone pay" before building billing — but they are not required to build the spine.

**Why not C (productize now):** the §0.3 moat audit is honest — we don't have a Day-1 customer-facing moat. Shipping a public SaaS today means immediately competing on price + sales motion + support quality with Lindy ($50–200/mo SMB), Notion ($10–18/user with free agents), Atlassian ($0 marginal for Atlassian customers), and Glean (enterprise sales motion we cannot match). We'd lose all four fights at the same time, while taking 60% of Sankalp's attention.

**Optional — covert design partners (still valid on A+, not required):** same bullets as the original draft — shared work with Consumer Brain, cheap market signal before billing, reversible, defers Stripe/public/SOC2 until there's evidence. Use this only if founder time allows; **A+ does not require external orgs.**

**Day-91 re-decision criteria** *— only if you opted into design partners; skip if A+ only*

| Outcome at day 91 | Decision |
|---|---|
| **3/3 design partners say "we'd pay"** AND multi-tenancy work is done in <8 weeks AND the moat audit (§0.3) has at least one row that improved from "future" to "real" | Flip to **C — Productize**. Public landing page, billing, first paid customer by day 120. |
| **2/3 say "we'd pay" but multi-tenancy isn't done** OR moat audit unchanged | Extend B another 90 days. Re-evaluate day 181. |
| **1/3 or fewer say "we'd pay"** OR design partners stop using it after 30 days | Flip back to **A — Stay internal forever**. Multi-tenancy work continues for Consumer Brain. Brain-as-OS becomes "Brain runs Paperwork Labs, full stop." This is a totally honorable outcome. |
| **All 3 design partners say "this is amazing but we'd never pay $X"** for any X you'd accept | Flip to **A**, with a honest "wrong wedge" post-mortem. Possible re-attempt with a different wedge in 12 months (e.g., RA firms or AI-native dev shops instead of generic 1–10p teams). |

**Design-partner selection criteria (3 max):**
- 1–3 person team
- Already running 5+ SaaS tools they complain about
- Technical-enough founder to debug their own integrations
- Pre-existing relationship with Sankalp or the company (NOT cold outbound — too much support load)
- Willing to be in a private Slack channel with you for daily questions for 30 days
- Explicitly told upfront: "this is free, no SLA, we may shut it down with 7 days notice, you may lose your data, please don't put anything irreplaceable in it"

**Day-0 to day-30 founder cost estimate for B:** ~3–5 hrs/week on top of the multi-tenancy engineering work that's happening anyway. If the partner relationships start consuming >5 hrs/week you've selected the wrong partners — re-pick.

### §0.5b — Quantified §0.5 trigger (locked 2026-05-04 per AI-CEO review)

The original §0.5 day-91 criteria ("3/3 say we'd pay" + "moat audit improves") were flagged as **half-falsifiable** ("we'd pay" is conversational) and **half-undefined** (no metric for moat delta, no scheduled refresh). Revised quantification — **ALL 4 must be true** before flipping internal-first → covert-design-partner → productize:

| Trigger | Falsifiable measure | Owner | Cadence |
|---|---|---|---|
| **Design-partner commitment** (replaces "we'd pay") | ≥2 signed design-partner LOI/email engagements with concrete scope + 30-day pilot start date | Founder + cofounder Olga (T0.1 pipeline) | Continuous; tracked in Conversation tag `partner-pipeline` |
| **Moat audit movement** (replaces "moat audit improves") | ≥1 row in §0.3 moat audit moves Red→Yellow OR ≥3 move Yellow→Green during quarter | Brain monthly digest (T3.15) refreshes table; founder ratifies quarterly | Quarterly review at end of Q2/Q3/Q4 |
| **Spine RLS health** (NEW) | ≥90% of multi-tenant tables have RLS enforced + passing cross-tenant negative tests in CI | T4.1 RLS rollout completion | One-shot at Spine done; verified weekly thereafter |
| **Real internal usage** (NEW) | `usage_meter row growth per tenant per week ≥ 100` (proves the gateway is actually consumed, not theoretical) | T4.2c meter wired + T4.4 rollup | Continuous; surfaced in `/admin/billing` |

**Until ALL 4 met**, GTM build (Stripe Checkout, public landing, sales deck, SOC-2 project) remains deferred. Founder cannot unilaterally override this gate without a written entry in `docs/KNOWLEDGE.md` documenting which specific trigger was waived and why.

The §0.5 day-91 re-decision criteria above (3/3 say we'd pay etc.) **are superseded** by this §0.5b table and retained for historical reference only.

### §0.6 — What this means for the rest of the doc

**§0.0 (internal-first + B2B-ready spine)** means: §§3–5 are **active engineering guidance** — not optional future fiction. Multi-tenancy, gateway, killing split-brain, Studio as coherent admin — all land in the **internal** milestone order. §§1–2–4–6–7 describe how that same spine *looks* when labeled for an external tenant (white-label, categories, packaging) so you don't redesign later; implementation priority follows §5.

| Path | How §§1–7 apply |
|---|---|
| **A+ only** | Build spine for `paperwork-labs` (+ `platform` org per D62). No second customer. §6 stays "threat awareness," not sales battlecards. |
| **A+ → B** | Same spine + provision 1–3 **staging or low-risk** external org rows; still no Stripe. §1–2 help positioning conversations; §5 adds a short "tenant provision" checklist. |
| **A+ → C** | Spine + billing + public commitments. §5 grows SLA + CS ops; not started until a falsifiable trigger (e.g. 2+ design partners say they'd pay). |

**Next doc chunk:** §1 Vision lock written for **REMEMBER + DO**, white-label-by-default, hybrid tenancy (shared+RLS SMB / per-DB enterprise) — all framed as *what we build toward* while internal dogfood remains the customer.

---

## §1 — Vision lock

> *Next chunk — locked to §0.0 (internal-first, B2B-ready spine).*

---

## §2 — The tool-category audit (the core)

> *Pending §0 + §1.*

---

## §3 — Multi-tenancy reality check

> *Pending §0.*

---

## §4 — Studio as the licensable UI

> *Pending §0.*

---

## §5 — What lands FIRST before licensing is even possible

> *Pending §0.*

---

## §6 — Risk + competitive positioning

> *Pending §0.*

---

## §7 — Bible patches (copy-paste-ready)

**Status (2026-05-03):** Landed **in-repo** in [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md). Read there instead of pasting from this file.

| Item | Where in the bible |
|------|-------------------|
| D64–D76 (Company OS, internal schema, conversations, transcripts, dispatch, verification, reference pipeline, dogfood, JSON→DB, phase naming, Studio tokens, schema co-ship) | [§1 Design Decisions](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md#1-design-decisions-d1d76) — search `### D64` … `### D76` |
| D70 + §8 Studio admin / nav matrix | [§8 Studio Dashboard](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md#8-studio-dashboard-admin--company-os-surface) + D70 pointer |
| Memory Moat → org scope | [D49](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md#d49-the-memory-moat-brain-as-universal-life-vault) — closing **Company OS extension** paragraph |
| Dual-context + Company OS | [D54](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md#d54-dual-context-architecture-founder-dogfood) — **Beyond founder dogfood** paragraph |
| PR #664 baseline (Reference Data + Gateway + MCP pointers) | Doc header **Doctrine baseline** + [Reference Data](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md#reference-data-storage-doctrine) + [Brain Gateway](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md#brain-gateway-architecture) |

Further deep-dive narrative and INTEGRATE/REPLACE matrices remain **future work** in §§1–6 of *this* strategy doc.

---

## §8 — Honest scope footer + open questions

> *Will be filled in last. Already know it includes: zero customer interviews done, zero financial model, zero security review, zero pricing validation, zero brand/domain research for the productized name.*

---

## TL;DR (so far — §0 + §0.0)

1. **Founder lock:** internal-first **and** keep B2B **easy later** — that means **build the spine** (tenant boundary, gateway, one source of truth per concept); **defer** billing, public GTM, SOC2 project, white-glove CS.
2. **Yes, you still need to build it.** Internal-only on split-brain JSON/SQLite is not "avoiding multi-tenant complexity" — it's **deferring a harder migration** while Consumer Brain and Studio still need the same bones.
3. **The market** (§0.2) is crowded with bundled agents (Atlassian/Notion/Microsoft) and SMB agent shells (Lindy/Relevance) — B2B is optional; the spine is not optional for a coherent Brain.
4. **Moat audit (§0.3)** is still honest: customer-facing moat accrues over time; plumbing + ops discipline is what you ship in 2026.
5. **Design partners (old §0.5 Option B)** are **optional** falsifiers — useful, not required for A+.

## Three hardest open questions I cannot resolve from this audit

1. **Are there 3 founder-friend shops that match the design-partner criteria, and will they actually use Brain instead of letting it gather dust?** — Cannot resolve from a code audit. Requires you to draft a list of 5–10 candidates and reality-check it with one phone call each.
2. **Does the multi-tenancy work, done correctly, slow down Consumer Brain by 4+ weeks, or is it genuinely shared infrastructure with no opportunity cost?** — Locked plan claims shared. I believe it's shared for Wave B + C, but the per-tenant onboarding/billing/SOC-2 surface is **net new work** that Consumer Brain doesn't need. Sizing this honestly requires 1–2 days of detailed planning by Sankalp, not a single Opus session.
3. **Is there a wedge we missed entirely that's bigger than 1–10p teams?** — I deferred to your Q1 ranking (a/b/d). But the §0.2 numbers suggest **AI-native dev shops** (10–50p companies that already buy Lindy + Relevance + Cursor + Linear and have a CTO with a budget for "agent infrastructure") might be a bigger and faster wedge than generic 1–10p teams. I didn't write a full §1/§2 around that wedge because you didn't pick it. If you want me to, I can re-run §1–§2 against it after §0 lands.

---

*§0.0 added per founder direction — internal-first + B2B-ready spine. Next: §1 Vision lock.*
