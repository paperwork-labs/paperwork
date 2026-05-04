---
last_reviewed: 2026-05-04
doc_kind: audit
domain: strategy
status: active
audience: founder
authored_by: composer-2-fast subagent (AI-CEO / Chief Strategy Officer persona)
product: [brain, platform, filefree, launchfree, distill, axiomfolio, studio, trinkets]
---

# Q2 Master Plan — AI CEO / Chief Strategy Officer Review

**Audience:** Founder + orchestrator
**Inputs:** [`paperwork_2026q2_master_plan_f9ce7c63.plan.md`](file:///Users/paperworklabs/.cursor/plans/paperwork_2026q2_master_plan_f9ce7c63.plan.md), [`BRAIN_AS_COMPANY_OS_AS_SERVICE_2026.md`](../strategy/BRAIN_AS_COMPANY_OS_AS_SERVICE_2026.md) §§0.0–0.5 + TL;DR, [`AGENTS.md`](../../AGENTS.md) §1–2, [`cfo.mdc`](../../.cursor/rules/cfo.mdc) (fixed burn + infra discipline).
**Date:** 2026-05-04

---

## Executive verdict (1 paragraph)

**Approve with conditions.** The spine-first lock (strategy §0.0) is strategically correct for a bundled-agent market where day‑1 differentiated revenue from "Brain‑as‑OS" is doubtful: you are buying **internal COGS**, **risk reduction**, and **optionality**, not immediate ARR — which matches pre‑revenue, solo‑dev reality. Top strategic concerns: (1) the plan still **overload‑scopes** Tracks 2–3 ("69 workstreams") against a human ceiling of ~90–120 orchestrator hours — under‑pricing founder review, merge-queue friction, and phone E2E; (2) **portfolio misalignment** persists: FileFree (North Star per `.cursorrules`) is materially under‑represented versus Studio/infra/Brain platform workstreams; deferring LaunchFree MCP (T5.5, XL, Q3) is acceptable for formation *trajectory short‑term*, but widens "MCP‑per‑product" doctrine asymmetry versus AxiomFolio + pending FileFree (T5.4); (3) the §0.5 GTM trigger as written (**"we'd pay" + "moat audit improves"**) is half‑falsifiable ("we'd pay" is conversational) and half‑undefined (no metric for moat delta, no scheduled refresh).

---

## Capital allocation review

**Per \$1 cheap‑agent ROI (expected):** Highest — **stop‑bleed + single sources of truth** that remove re‑work classes: **T1.0a–c**, **T1.0d** (Conversations Postgres, blocks Track 2 + T4.1), **T2.0** (goals triple‑source killer), **T2.16** (labels spine before snapshot kill — plan correctly sequences "before T2.10"), **T1.2** (autopilot `install()`), **T5.1** Wave K3 (reference‑data duplication = legal/regulatory‑class drift). Lowest — diffuse **audit‑for‑audit's sake**: **~12× T3.3** runbooks ahead of existential smoke (unless REGISTRY‑gated incremental), optional **T3.5** Slack streamline (already P3), and **brand polish** cross‑cut ("5× S, P3") while pre‑revenue. **Cut candidates (if preserving 10–11 wk variant):** the plan already lists dropping **T5.13/T5.14**, **phase‑2 snapshots** (8 files needing **T2.10a first**); I would add conditional skip: **T3.14** layer‑upgrade execution unless tied to outage/cost regressions (**T3.4** warns first).

**Per founder orchestrator hour — best:** **T1.0d** correctness, **T4.1** RLS rollout risk, **gateway split** (**T4.2a–c** — plan's 3‑sub‑WS decomposition is strategically sound vs one "L‑shaped blob"), **T5.6** `pwl` CLI (compounds every future week), merged queue / protected‑regions review per `cheap-agent-fleet.mdc` Rule #3. **Worst:** serial **T2.10** thirteen snapshot kills requiring **brain endpoint exists** + **navigation + phone E2E** each — high context switching versus **delegating mechanical PRs once contracts are frozen**. Also **Tier‑2 labels (T2.18)** needing founder adjudication (**T2.19**) eats calendar, not \$.

**Buying speed vs patience:** **Buying speed:** **T3.11** staging (\$7/mo Render Starter in **cfo.mdc** framing) vs staging RLS on prod nerve — patience is false economy. **Patience cheaper:** **T3.14** broad "execute every REPLACE/UPGRADE" within 14d of audit — overlaps **T5.9** novelty risk; time‑box tighter or gate on incident/cost triggers.

**§0.5 trigger realism ("3 say we'd pay" + moat improves):** "We'd pay" is noisy without **price anchor + LOI/email commitment** — three friends verbalizing is survivorship bias. **"Moat audit improves" has no reviewer, cadence, or measurable row movement** vs §0.3 table (strategy doc explicitly says bible moats lagged operational reality). Better trigger (still deferring Stripe/SOC2): **≥2 signed design‑partner engagements** OR **\$X pre‑commercial pilot fee** routed manually (invoice/ACH, not Stripe Checkout) plus **explicit moat deltas** measured quarterly (examples: `% gateway invocations succeeding`, `% tables RLS‑enforced with CI cross‑tenant negatives`, **`usage_meter` row growth per tenant**, NPS‑style founder survey ×3). Keep **Stripe Checkout blocked** until you need metered invoicing-scale.

**\$150 scaling with 69 workstreams:** Not linear. **Non‑linear hotspots:** **T4.1 RLS** (L — query audit blast radius ≥30 surfaces), **T3.1** IaC drift (L — reconcile semantics + credential scope **T3.1‑pre** prerequisite), **T2.18** LLM‑inferred transcripts/conversations (**cost AND founder review queue entropy** — plan's \$10–30 is infra only), **T5.9 self‑improvement** (L — governance + revert risk exceeds token line items), **T5.6** CLI (L), **T5.5** XL off‑path (correctly flagged). Composer‑fleet \$80–\$150 excludes **mistake multiples** — a bad migration under **migration ordering constraint (T2.4 → T1.5 sequential)** blows weeks, not \$.

---

## Product portfolio strategic check

**Proportionality:** By workstream labeling and cost split in plan (**T2 ~\$40/~22 WS**, **T3 ~\$30/~17 WS**, **T5 ~\$50**/IP + autonomy, **Track 1 "Make Brain Real"**) the center of mass is **Studio + Brain + platform spine**, **not FileFree monetization primitives** (EFIN/transmitter timelines in `.cursorrules` are scarcely enumerated as Q2 milestones). Distill ("B2B revenue path") is mostly **infra + gateway + MCP pointer pattern** (**T5.4**/Track 4) — coherent with §0 deferral of customer SaaS, but **thin on Distill SKU delivery** explicitly. **AxiomFolio** gets operational cover via MCP reference + ingestion (**T2.20** transcript import tilt) versus FileFree‑scale surface work.

**Four‑axis labels (T2.16–T2.20) as P0:** Correct: plan states **must land before T2.10 snapshot kill** (**T2.16** acceptance + CI guard pairing with D76) — aligns with founder "pre‑user = no historical drift".

**Founder first sprint post‑L4 (plan silent):** Recommend FileFree wedge tied to transmitter north star: ship one **user-visible** credibility increment (pick one: OCR→calc fidelity demo end‑to‑end, taxpayer consent/EFIN onboarding slice, filing submission hardening spike) unless partnerships pipeline urgently needs a DemoFree artifact — rationale: `.cursorrules` North Star explicitly FileFree‑biased; deferring LaunchFree MCP does **not** block that choice.

**T5.5 LaunchFree MCP to Q3 — acceptable strategically** for LL formation *if* roadmap promise is Distill Formation API/FileFree MCP first and LaunchFree consumes shared **filing‑engine** port. **Starvation risk:** real if partnerships or Delaware automation pilots need MCP parity before Q3 — monitor for **explicit external dependency** emerging from cofounder lane; mitigate by **narrow DE stub** MCP (read‑only/status) versus full **`playwright-python` port**.

---

## Sequencing risk: critical path & dependencies

**Longest path → T5.9 ("L5 ACTIVATION"), one serial reading of the DAG (no double‑count parallelism), honest week rollup:** Interpret each major gate as elapsed calendar dominated by merges + staging burn‑in (not naive sum of XS labels):

| Segment (IDs) | Weeks (plan‑consistent, conservative single‑thread spine) |
|---------------|------------------------------------------------------------|
| T1.0a–c bleed + **T1.6** hooks | ~1 |
| **T1.0d** Conversations Postgres (**M**, P0) | ~2 |
| **T2.0** goals unification (**M**, P0) — parallel with bible/autopilot ops but binds labels entry | ~2 |
| **T2.16–T2.19** migration + deterministic + infer + swipe queue (**M**/parallel batches) | ~2 |
| **T2.10a → T2.11 → slice of T2.10** snapshots (minimal gate before spine claim) — plan implies ~2 calendar if parallel PRs succeed | ~2 |
| **T3.11** staging (XS flagged but calendar + Neon branch reality) nestled with **T3.0**/audit front | ~0.5–1 overlapping |
| **T4.1** RLS + 24h burn‑in (**L**) | ~3–4 |
| **T4.2a→b→c** gateway stack + MCP client + metering before **T5.4** | ~3 |
| **T5.1→T5.3** hygiene + MCP package (**M+M**) | ~2 |
| **T5.4** FileFree MCP (**M**) + **T4.6** tenant provision (**S/P1**) + **T44/T54** metering convergence | ~1 overlapping |
| **T5.6** CLI (**L**) + **T5.7** onboard 5 apps | ~2–3 |
| **T5.8.5 → T5.8 → T5.11 → T5.9** (S→M→S→**L**) | ~3–4 |

**Rolling sum ≈ ~21 calendar‑week‑equivalents** if forced serial. **The plan's 12–14 wk honesty** requires aggressive overlap (diagram shows intentional parallel fan‑out **T13/T14**, **Track 3 stack audit**, **T5.1**) — believable **only if merge queue friction stays low.** If any **M/L** slips a week twice, calendar hits ~16–18. **Longest schematic chain on diagram wording:**
`T1.0a–c → T1.6 → T1.0d → T2.0 → T2.16 → {T2.17|T2.18} → T2.19 → (Spine parallelism) meanwhile Track3→ T3.11→ T4.1 → {T4.2*} → join T5.1→T5.3→T5.4/T4.4 convergence → T5.6 → T5.8.5 → T5.8 → T5.11 → T5.9` — bottleneck nodes are **`T1.0d`, `T4.1`, gateway stack, `T5.6`, `T5.9`.**

**Parallelization gaps:** **T3.0 / T3.0a / T3.7 / T3.8** could start earlier versus waiting on "mental Track 3 start"; plan diagram already partially shows **T10→T30** early — operationalize literal week‑1 trio after bleed patch. **Convoy/high fan‑out:** **`T10d`** (blocks Track 2 + **T4.1**), **`T216`** (+ **T2.10** family), **`T42a`** (gateway root), **`T56`** milestone — sizing appropriate only if RLS/gateway each get reserved founder blocks, not squeezed between snapshot PRs. **Single‑point slip (+1wk plan slip): `T1.0d`, `T4.1`, `T5.6`** (pick three; also **`T41/T311` pairing** if staging delayed).

---

## Founder energy & morale risk

Morale hazard is **high**: 12–14 wks × daily diff‑review (**cheap-agent‑fleet.mdc** Rule **#3**) + phone E2E on **many** Track 2 rows + infra firefighting — classic **infra treadmill** resentment by **wk 7–9** absent revenue dopamine. **Emotional anchors every 2–3 wks (plan‑native):** "stop bleed merged" (**T1.0a–c**), "Conversations won't evaporate" (**`T10d`**), Goals single brain (**`T2.0`**), Labels live + queue clearing (**`T2.16–19`**), SpineDone checklist (**milestones §**), **`T5.6`** demo CLI PR (tangible multiplier artifact), **`T5.9`** first autonomous brain PR landed (risky euphoria if sloppy — pair with rollback story **T3.6** kill switch narrative).

**T2.20 cross‑machine ingest:** Genuine **personal tool win** ("axiomfolio laptop tarball") improving trust in Brain ingestion — **but M/P1**, not XS; tariff includes security review spike (tarball ingestion is **supply‑chain-y** mentally even if scoped internal token).

**"Too painful" workstream candidates:** **`T3.14` omnibus upgrades** feels productive but steals cycles from visible product; **`T3.9` migrating ~50 workflows** policy enforcement is boring but bill shock linked — reconcile by visible **\$ delta** dashboards (**T3.4**). Rescope: **tier‑0 workflows first** enumerated in **REGISTRY (T3.2)**.

**Handling "infra quarter, nothing to sell" by week ~8:** Reframe SpineDone as **`T5.4` invokes real tax MCP** producing **measurable artifact** ("calculated return snippet export") — pseudo‑SKU demo without Stripe; pair with **weekly partnership narrative** cofounder‑visible (pipeline stages, qualitative quotes) stored as **Brain Conversation tags** (`partnerships` analog) though strategy defers SaaS. **Do not pretend moat matured—publish internal scorecard §0.3 rows Red→Yellow moves.**

---

## Brain-as-Service GTM readiness check

**After Spine (~wk 8–10), could a paying design partner onboard? Structural readiness vs §0.0 "days not quarters."** Roughly yes on **infra primitives** if **REGISTRY**, **staging tenant provision <5 min (**T4.6**)**, **RLS proofs**, **`usage_meter` accrual**, **`brain.invoke`**, `brain_user_vault` exercised — aligns with Spine acceptance gates (**plan §Milestone acceptance**). Still missing for an actual commercial motion (yet allowed pre‑Stripe per §0.5): minimal **sales artifact** pack (problem statement + security boundaries + allowable data domains), **trial agreement template** (still not "sales deck/marketing", but legal hygiene), **`/admin/billing` read‑only rollup** (**T4.4**) proving internal chargeback math — partially in plan. **Not covered adequately:** scripted **weekly success checkpoint** questionnaire for beta orgs. **Minimum add violating neither §0.5:** **`Track 6 skeleton` — 90‑min founder monthly partner pipeline review + 1‑pager internal** (draft only) + **explicit data deletion path** citation (strategy §0.4 item 10 flags gap).

**Tenant provision "<5 min (**T4.6** elevated P1)" alone ≠ GTM** — pairing needs **credential mint ritual + scope matrix + kill switch familiarity** (**T3.6**). Plan partially covers via **Secrets rotation (**T2.9** + **T3.13**) and **credential expiry cron** (**AGENTS.md** §4**) but not conversational sales scaffolding.

**Moat audit refresh schedule missing:** Align with §0.5 wording — designate **WHO (founder or quarterly Brain summary job starting post‑`T5.8`), WHEN (calendar Q2‑06‑30 midpoint + SpineDone), METHOD (duplicate §0.3 table annotate deltas)**. **Without this**, second trigger clause is veto‑bait.

---

## What's missing strategically (cap 5)

1. **What:** Competitive / bundled‑incumbent monitoring cadence (Notion beta pricing churn, Copilot roadmap noise) → **compact monthly scan + §0.2 table refresh**. **Why now:** §0.2 externalities degrade wedge monthly — waiting Q3 blinds pricing later. **Effort:** 2 hrs/mo. **Placement:** Fold into **Brain scheduled digest** (**T5.8** precursor) — **mini Track 6 §Intelligence.**

2. **What:** Formal **design‑partner cultivation pipeline spec** separate from covert ops story (strategy §0.5 Option B) — stages, disqualifiers, churn signal. **Why now:** If trigger is partner‑dependent, inbound randomness wastes spine investment. **Effort:** 1 founder half‑day scaffold + upkeep 30 min/wk. **Placement:** **NEW Track 6 (lightweight)** or **Brain Conversation tagging schema only**.

3. **What:** **Cofounder revenue enablement pack** ("what Olga can sell next 90 d without Shopify/SaaS scaffolding") aligning partnerships lane with infra reality. **Why now:** Pre‑revenue company emotional balance—prevents divergence narrative. **Effort:** 3–6 hrs once. **Placement:** Strategy doc pointer + **`OBJECTIVES.yaml` weight tweak (**T5.8.5**)**.

4. **What:** **Financial runway bridge narrative** marrying **infra additions** (**T3.11** \$7+/mo increments) against **\$0 revenue** CFO baseline (**cfo.mdc** infra <\$50 aspiration). **Why now:** Staging pushes fixed costs—risk of creeping past guardrail unnoticed. **Effort:** 1 hr model update + **`/admin/cost` projection linkage (**T3.4**) acceptance**. **Placement:** **Track 3** acceptance gate.

5. **What:** **`T5.9` constitution** — rollback triggers, autonomy budget cap, anomaly detection interplay (**`T5.12`**) prerequisites sequencing clarifier. **Why now:** L5 activation prematurely credibly nukes nightly sleep. **Effort:** 0.5–1 wk policy writing (founder-heavy). **Placement:** **Immediately precede `T5.9`** (split policy vs code).

---

## Risk register (top 5)

| # | Risk | L | Impact | Mitigation in plan | Additional |
|---|------|---|--------|---------------------|--------------|
|1| **Migration ordering / Alembic head collisions** (**T2.4** before **T1.5**) cause branch pile‑ups | **H** | Stops merges + freezes parallel fleet | Sequential merge note (**T244/T1.5** constraint) | Enforce **`alembic heads` CI gate artifact** surfaced in Conversation |
|2| **RLS flip exposes latent unscoped queries** | **M** | Cross‑tenant leak / outage | staged **T4.1** + **T3.11** prerequisite | Canary SQL negative tests enumerated pre‑flip checklist |
|3| **Founder burnout / throughput collapse** | **M** | Timeline slips nonlinearly (>2 wk) | cadence reminders (carry‑forward block) | **Hard cap active parallel M/L** (`≤2`), weekly kill of lowest ROI open WS |
|4| **`T5.9` autonomy PR triggers prod regression** | **M** | Trust collapse in Brain doctrine | **`T5.11` gradual self‑merge`,`T3.6` kill‑switch**/self‑revert | Require **`T512` anomaly before broaden merge** graduation |
|5| **GTM trigger never fires** ("moat improves" vagueness traps in internal‑only indefinitely) | **L–M** | Opportunity cost vs FileFree monetization momentum | Spine still aids consumer Brain (**strategy §0.4 items 5–10**) | **Quantified moat delta + quarterly refresh** |

---

## Approval recommendation

**APPROVE WITH CONDITIONS**

**Conditions (3–5):**

1. **Define §0.5 quantitatively**: replace ambiguous "moat improves" with **≥2 observable metric thresholds OR explicit row state changes tracked quarterly** (**owner assigned**).

2. **Cap concurrent L‑class merges** (**T4.1 gateway `T5.6`, `T5.9`,`T3.1`**) — maximum **two** simultaneous deep reviews; serialize snapshot wave if needed.

3. **Portfolio guardrail milestone**: Schedule **minimum one contiguous 1‑week FileFree‑labeled founder block** post‑ **`T52` completeness** (**`T54` MCP live** milestone) ahead of discretionary **`T514` procedural consolidation**.

4. **Moat/competitive refresh cadence** added (lightweight) **before SpineDone retrospective**.

5. **`T52` anomaly (`WS-50`) default ON before expanding `T5.11 self‑merge` promotion velocity** toward **`T509`**.

---

*All 5 conditions addressed in plan patches landed 2026-05-04. See [`docs/KNOWLEDGE.md`](../KNOWLEDGE.md) D94 + [`docs/strategy/BRAIN_AS_COMPANY_OS_AS_SERVICE_2026.md`](../strategy/BRAIN_AS_COMPANY_OS_AS_SERVICE_2026.md) §0.5b.*
