---
title: Brand & Design System Deep-Dive (2026 Q2)
owner: brand
last_reviewed: 2026-04-25
doc_kind: sprint
domain: company
status: research
sprint:
  start: 2026-04-25
  end: 2026-05-16
  duration_weeks: ~3
---

# Brand & design system deep-dive (2026 Q2)

**Purpose**: Give Sankalp and the team a McKinsey-style evidence stack for whether Paperwork Labs should unify on the AxiomFolio-inspired blue + gold system, what it costs in product and engineering terms, and what decisions are blocking execution.

**Confidence**: *Medium–high* on *inventory and competitive framing* (grounded in repo tokens and public brand norms). *Medium* on *recommended palette* (synthesis, not user testing). *Low* on *logo outcome* (brief only — no design deliverable here).

## 1. Executive summary

Paperwork Labs should **treat AxiomFolio’s blue + gold as the default “company family” direction**, with two caveats: (1) **rebalance roles** so blue carries trust and navigation (as it already does in AxiomFolio data surfaces), while **gold is an accent, not a default body or small-text color** — #FACC15–class yellow fails WCAG on white (~1.5:1 for normal text; verified computationally) and must never be the only differentiator. (2) **Do not force one flat palette across all products** without sub-brand nuance: the repo already encodes per-product `data-theme` palettes in `packages/ui/src/themes.css`; the lowest-regret path is a **shared structural neutrals + shared primary blue + per-product accent** (Option B below).

**Cost**: Moderate, not trivial — roughly **0.5–1.0 engineer-week** to centralize tokens and flip apps once decisions are firm, plus **2–3 designer-days** for logo exploration if taken seriously. The larger cost is *coordination* (marketing, product naming, landing pages) if you re-skin multiple consumer funnels the same week.

**Case for**: One coherent trust signal across finance, tax, and “paperwork” tools; AxiomFolio already proves the system in a public-grade surface; blue is legible on dark (e.g. blue-400 on slate-900 ~7:1) and works for enterprise-adjacent products (Distill, Studio).

**Case against**: Blue is the default fintech “uniform”; gold can read *crypto* or *2010s premia* if overused. FileFree, LaunchFree, and Trinkets have **deliberate** emotional palettes today (violet, teal, amber) that differentiate categories — squashing them without a sub-accent strategy would make products feel interchangeable.

**What Sankalp must decide (target: 2026-05-16, after Streamline+SSO window cools)**: (1) single palette vs shared base + per-product accent, (2) whether gold stays *literally* in the AxiomFolio range or shifts warmer/colder for 2026 taste, and (3) **whether to fund a real logo process** (paperclip) vs. a temporary wordmark-only stack. No code in this research PR — **implementation** should start only after `docs(brand): …` and explicit scheduling against [STREAMLINE_SSO_DAGS_2026Q2](STREAMLINE_SSO_DAGS_2026Q2.md) (~close 2026-05-09).

## 2. Current state inventory

| Product / surface | Primary (token or rough) | Accent / secondaries | Logo status | Stack | Where tokens live | vs `packages/ui/src/themes.css` |
| --- | --- | --- | --- | --- | --- | --- |
| **Studio** | HSL `0 0% 98%` “white” primary (neutral) | Gradient zinc `#71717A` → `#52525B` | Pending per `.cursor/rules/brand.mdc` | Next (Tailwind v4) | `packages/ui` → `[data-theme="studio"]`; `apps/studio/src/app/globals.css` overrides to zinc dark | **Aligned** with shared theme; globals duplicate studio HSL for `:root` |
| **FileFree** | HSL `238 76% 57%` indigo-leaning | UI accent slot is *muted purple surface*; brand gradient violet → purple; charts use sidebar tokens | Wordmark / monogram pending | Next | `themes.css` `[data-theme="filefree"]`; `apps/filefree/src/app/globals.css` adds light `:root` + dark `.dark` (marketing vs app mix) | **Diverges**: globals define **light-first + dark** local tokens (sidebar, charts) in addition to shared theme; not “wrong,” but not single-source |
| **LaunchFree** | HSL `174 70% 35%` teal | Cyan in gradient `#14B8A6` → `#06B6D4` | Pending | Next | `themes.css` `[data-theme="launchfree"]`; `apps/launchfree/src/app/globals.css` **minimal** (slate-950/50 only) | **Mostly uses shared** theme; app shell forces slate body classes — **intentional** “dark on slate” feel |
| **AxiomFolio (Vite)** | OKLCH: `--primary` is **high-chroma gold/amber** (not blue); “brand blue” lives in `rgb(29, 78, 216)` auth gradient, `--chart-equity` / series blues | Gold as shadcn primary; blue as chart + selection + brand glow | Distinct product identity (incl. glyph) in app | Vite + Tailwind v4 | `apps/axiomfolio/src/index.css` (oklch + RGB semantic layers, color-blind `data-palette="cb"`) | **Intentional split**: CTA/primary token reads gold; data + auth hero reads blue — **this is a feature, not a bug** for finance UX |
| **AxiomFolio-Next** | Same as Vite (copied `axiomfolio.css`) | Same | N/A (port) | Next | `apps/axiomfolio-next/src/app/globals.css` imports `@paperwork-labs/ui/themes.css` + `./axiomfolio.css` | **Shared UI package** + AxiomFolio-specific overlay; migration path to converge company tokens later |
| **Distill** | HSL `217 91% 60%` blue + slate | Gradient blue → deep blue; rose/shadcn destructive | Pending | Next | `themes.css` `[data-theme="distill"]`; `apps/distill/src/app/globals.css` slate-900/50 | **Aligned** theme; thin globals |
| **Trinkets** | HSL `38 92% 50%` amber | Orange in gradient; stone background | N/A (utility) | Next | `themes.css` `[data-theme="trinkets"]`; `apps/trinkets/src/app/globals.css` stone-950 / amber-50 | **Aligned** theme; thin globals |

**Honest read**: AxiomFolio is the only surface with a **mature, product-grade** visual system (oklch, semantic status colors, color-blind chart palette, elevation). The other apps are **coherent shadcn-style shells** with per-`data-theme` differentiation but **less narrative polish**. Studio is *deliberately* almost monochrome. That is a strategy choice (internal/ops) — not a gap by accident.

## 3. Competitive landscape (reference brands)

This section is **analytic**, not a trademark survey — the goal is *positioning language* Paperwork can reuse or reject.

**Stripe** — *Decision*: Own **purple** and confident motion so “payments” feels designed, not utilitarian. Stripe borrows: **gradient + glow as a signal of premium infrastructure**. Reject for PLabs if you need to feel calmer and more regulated than a developer API brand.

**Linear** — *Decision*: **One memorable hue (eggplant)** and ruthless monochrome elsewhere; speed and taste through restraint. Borrow: *Fewer token decisions per screen* (cognitive load). Reject: hyper-minimal if consumer tax products need warmth.

**Vercel** — *Decision*: **Black, white, and word-as-logo**; brand = typography, not color emotion. Borrow: a strong monogram (triangle) is enough at small sizes. Reject: total austerity for FileFree/consumer trust.

**Mercury** — *Decision:* **Terracotta + cream** to feel *human bank* vs crypto-chrome. Borrow: *Warm neutrals* reduce “scary finance.” Reject: orange-forward if you must stay in “blue = trust” lane for compliance products.

**Notion** — *Decision:* **Neutrals + one accent**; the product is “paper.” Borrow: *Background is never loud* — good for “paperwork” umbrella. Reject: low chroma if every sub-brand must pop in ads.

**Wealthfront** — *Decision:* **Deep blue + growth green** — classical trust + upside. Borrow: *Two-color story is enough*; avoid five accent hues in one dashboard. Reject: green if you already have success semantics elsewhere.

**Robinhood** — *Decision:* **Neon green as tribal identity** — maximal energy, not trust-first. Borrow: *single accent that users recognize from afar* (e.g. gold chip if disciplined). Reject: gamified connotations for B2B/Distill.

**Public.com** — *Decision:* **Black/white with one social accent** — brokerage as a modern *club*. Borrow: *restraint in UI chrome* so content (community, tickers) carries emotion. Reject: community-first model if not your roadmap.

### 2×2: Trust ↔ Energy (X) vs Restraint ↔ Expressive (Y)

| Region | Where it feels | References (approximate) |
| --- | --- | --- |
| **High trust, restrained** | Boring-in-a-good-way compliance | Notion, parts of Linear |
| **High trust, expressive** | Confident, still institutional | Wealthfront, Stripe (marketing) |
| **High energy, restrained** | “Serious fintech for younger users” | Mercury (arguably mid-high trust, warm) |
| **High energy, expressive** | Retail trading / cult brand | Robinhood |

**AxiomFolio (blue in charts + gold primary)** — approximately **high trust, mid–high expressive**: data surfaces feel institutional; CTA/primary gold adds **luxury/attention** (energy) without going neon.

**Where Paperwork Labs should sit (recommendation)**: **Upper-right of the “high trust” half** — strong restraint in chrome and neutrals, **one expressive pair** (blue structure + gold highlight) for consumer surfaces; let **sub-product accents** (violet, teal) move the dot *horizontally* ~10–15% for category differentiation without a second corporate identity.

## 4. AxiomFolio palette as company palette: pros / cons

**Pros**

- **Already vetted in-product** — AxiomFolio is not a mood board: color-blind `data-palette="cb"`, series separation, and auth hero gradients are implemented.
- **Semantically aligned to finance** — blue codes as structure/trust; gold codes as *premium* and *attention* in wealth UI (when used sparingly).
- **Dark-mode native** — Most Paperwork UIs are dark-first (see `.cursor/rules/ux.mdc`); on dark, yellow/gold tints (e.g. #FACC15 on slate-900) achieve **>10:1** contrast for text-like usage (computed), and blue-400 on slate-900 is **>7:1** — well above WCAG AA for text.

**Cons**

- **Blue is crowded** — Plaid, many banks, Coinbase (blue), generic “Trust SaaS” — *differentiation must come from motion, typography, and logo*, not from hue alone.
- **Gold risks cheap heat** if it appears in gradients on every CTA, or in crypto-adjacent pairings. Mitigation: **treat gold as “highlight and achievement,”** not “every button.”
- **Cross-product association** — If FileFree/LaunchFree **look** like AxiomFolio, users may *assume* shared accounts or a single “finance super-app.” That may be *desirable* (SSO story) or *risky* (category confusion) — a **product** decision, not a pure design one.
- **Light-mode accent fragility** — Brighter gold on white is **not** viable for 14px text (example: #FACC15 on #FFFFFF ≈ **1.5:1** contrast, vs AA 4.5:1 for normal text). AxiomFolio’s implementation already pushes gold through **oklch primary**; any company-wide adoption must add **a darker gold for small text** on light (e.g. ~amber-800 class contrast **~5.0:1** on white in quick checks) or reserve bright gold to large type / icon fills only.

**Accessibility headline**: Use **blue for interactive affordances on light/dark** at scale; use **gold for chips, large headings, sparklines, and “success/celebration” moments**, not for paragraph copy on white.

## 5. Recommended palette (concrete HSL tokens)

> **Format note**: The shared theme file uses `H S% L%` *without* the `hsl()` wrapper, matching `packages/ui/src/themes.css`. Below, **AxiomFolio “current”** is summarized: UI `--primary` is oklch-amber in code, while “brand blue” in RGB is ~`29 78 216` and chart blues ~`37 99 235` (see `apps/axiomfolio/src/index.css`).

| Token | Proposed (company) HSL | Rationale (short) | AxiomFolio / repo anchor | Change? |
| --- | --- | --- | --- | --- |
| `--primary` | `221 64% 45%` | Deep institutional blue; readable on light backgrounds with white `primary-foreground` | ~`#1D4ED8` / `1E40AF` range in spirit | Slightly *systematizes* toward one blue across Distill + Axiom |
| `--accent` (company highlight) | `45 96% 51%` | In family of #FACC15; **for large UI only**; pair with a dark `accent-foreground` on fills | Gold oklch primary feel | Tighter definition vs scattered ambers |
| `--accent-foreground` (if using accent for solid fills) | `222 47% 11%` | Dark text on gold buttons | n/a | New explicit pairing |
| `--background` (dark) | `222 47% 11%` | Aligns Distill/Studio slate family | AxiomFolio `bg` oklch ~slate-900 in `.dark` | Unify *family* of dark |
| `--background` (light) | `0 0% 100%` | Keep paper-white apps readable | AxiomFolio :root white | Same |
| `--foreground` (dark) | `210 40% 98%` | High-contrast body | Shared pattern | Same |
| `--foreground` (light) | `222.2 47% 11%` | Text on white | shadcn default family | Same |
| `--muted` | `223 47% 11%` (dark) / `210 40% 96%` (light) | Surfaces and hovers | Existing themes | Largely same |
| `--muted-foreground` | `215 16% 57%` (dark) / `215 16% 47%` (light) | Secondary labels | Existing | Same |
| `--success` | `142 76% 36%` | Distinguish from blue primary | AxiomFolio `status-success` family | Aligned to green, not “blue=good” |
| `--warning` | `38 92% 50%` | Amber, distinct from gold *accent* | `status-warning` / amber | Keep semantic, not brand-gold |
| `--destructive` | `0 84% 60%` (light) / `0 63% 31%` (dark) | Error | shadcn defaults | Same |
| `--info` | `199 89% 48%` | Sky — different from `primary` blue in charts | AxiomFolio `series-5` / sky | For banners, not CTAs |
| `--chart-1` | `221 84% 53%` | Brand blue in charts (matches `--series-1` comment) | AxiomFolio | Same story |
| `--chart-2` | `142 76% 36%` | Green series | AxiomFolio | Same |
| `--chart-3` | `38 92% 50%` | Amber series | AxiomFolio | Same |
| `--chart-4` | `265 92% 65%` | Violet | AxiomFolio | Same |
| `--chart-5` | `330 81% 60%` | Pink (distinct in CB modes if tuned) | AxiomFolio | Same |

**What stays** from AxiomFolio: **oklch pipeline + semantic tokens + `data-palette="cb"`** (do not throw away; it is a competitive feature).

**What changes** in a *future* code pass: **one canonical `--primary` blue in HSL/OKLCH** for “Paperwork” chrome across marketing + apps, with **gold elevated to a named `--brand-highlight`** if we need a slot separate from `--warning` amber.

## 6. Per-product theming strategy

| Option | Description | When it wins | Failure mode |
| --- | --- | --- | --- |
| **A. Single palette** | All products use identical `primary`/`accent` | Maximum corporate coherence; cheapest QA | **Category blur**; ads and SEO lose instant visual hooks |
| **B. Shared base + per-product accent** (recommended) | **Shared** neutrals, primary blue, chart ramp; each product **overrides** one *accent* slot (or gradient pair) for marketing differentiation | “One family, many doorways” — matches existing `[data-theme]` | Needs **rules** for when a screen is “company” vs “product” (e.g. Studio vs public FileFree) |

**Recommendation: Option B.** The repo is already structurally B — `packages/ui/src/themes.css` is the spine.

**If B, example accent overrides (HSL only; illustrative)**

| Product | Per-product accent (use for key CTAs, gradient end, *not* for all text) | Notes |
| --- | --- | --- |
| AxiomFolio | `45 96% 51%` (gold) | **Canonical** “wealth highlight” |
| FileFree | `263 70% 50%` (violet) | Preserves *calm / magic* in tax |
| LaunchFree | `189 85% 38%` (teal) | *Momentum* and formation energy |
| Distill | `221 64% 45%` (align to `--primary` — could be *no* override) | B2B: **no extra sugar** |
| Trinkets | `32 95% 44%` (amber) | Stays *utility* warm |
| Studio | `240 5% 64%` (zinc) | Stays *internal tool* (may override primary to zinc forever) |

## 7. Logo concept brief — “Paperclip”

**You are not receiving a design here; this is a creative brief for an external designer or a future generative/vector pipeline.**

- **Rationale** — A paperclip is a *binding* metaphor: contracts, tax packets, cap tables, and founder docs are “held together” by small tools. It maps to **Paperwork Labs** as the umbrella, not to any one SKU.
- **Hard constraints** — (1) **Favicon 24px**: single-shape silhouette, no hairline details. (2) **Monochrome** variant for invoices, press, and GitHub. (3) **Large lockups** to 1024px with no loss of intent. (4) **Rotation**: mark should remain legible at 0°, 90°, 180° (paperclips are *not* fully symmetric; pick a design that is *stable*, not random when rotated). (5) **Pair with a wordmark** — icon alone is not enough at Series A/B comms quality.
- **Style references (verbal)**
  - *Geometric reduction* (Vercel triangle): fewer anchor points, mathematically clean.
  - *Approachable weight* (Mercury’s rounded forms): not brutalist, not fintech-angular.
  - *Negative space tension* (FedEx arrow): optional hidden “P” or “link” read at second glance, but **do not** require it for comprehension.
- **Three directions to explore** — (1) **Literal** rounded paperclip, slightly customized tail length for uniqueness. (2) **Abstract** continuous loop: clip → *infinity* → “always connected” (careful: infinity reads *crypto*; pair with serious typography). (3) **P-negative-space**: paperclip *forms* the counter of a **P** for “Paperwork” while staying abstract enough for favicon.
- **Wordmark pairing** — *Inter* for neutral tech (already in org guidance; see `.cursor/rules/brand.mdc` / `ux.mdc`). *Söhne or GT America* if PLabs wants a **Khoi-level** raised editorial feel for investor decks only. *Tiempos* for long-form *manifesto* pages — not for app UI.
- **Color on surfaces** — On **dark** product UIs, logo defaults **white** or **1-color blue**; **gold** only in *hero* or *earned* moments (funding, annual report) — *never* on dense tables. On **light** marketing, **navy/charcoal** wordmark with optional gold dot or clip; **no yellow wordmark** on white at small sizes.

## 8. User-behavior considerations

- **Dark vs light default** — `.cursor/rules/ux.mdc` states *mobile-first, dark default* for most products, but AxiomFolio and FileFree *support* light. The proposed palette must **QA both**, with special attention: **light mode = blue CTAs, not gold text-on-white.**
- **Color blindness** — Protanopia / deuteranopia: blue–yellow anchors remain *more separable* than red–green *if* success green is not chart-only paired with similar blues at equal luminance. Tritanopia: blue vs teal confusion risk — *do not* put **teal and blue** in the *same* two-hue competition state without iconography. **AxiomFolio’s Okabe–Ito mode** is already the right engineering escape hatch; company palette adoption should **preserve** a global switch or auto preference.
- **Cultural** — *Gold* reads as *wealth* and *prize* in the US fintech context; it can also read *casino* if paired with *too much* black and neon. *Blue* reads as *trust* and *stability*; it can also read *bland* in a crowded market — mitigate with *layout and motion*, not *more color*.
- **Cognitive load** — Today, PMs reason about: `data-theme` + per-app `globals` + (Axiom) oklch + marketing site. A migration should collapse to: **(1) choose theme, (2) pick layout template, (3) never hand-pick hex** — everything routes through `themes.css` + semantic state tokens (success, warning, info).

## 9. Migration plan (future engineering)

1. **Update `packages/ui/src/themes.css`** with shared neutrals + blue primary + per-product optional `--product-accent` (or document gradient pairs only). *Rough diff*: **30–80 lines** touched (the file is ~180 lines today) depending on how aggressively we add semantic slots (`--brand-highlight`, etc.).
2. **Per-app `globals.css`**: `studio`, `filefree`, `launchfree`, `distill`, `trinkets` each have **5–20 lines** of overrides today — expect **+10–30 lines** per app if we align charts/sidebars, **or** *net reduction* if we delete duplicated HSL in favor of theme-only. FileFree is the **largest** merge surface (sidebar + light/dark + charts).
3. **Per-product accent (Option B)**: Implement as **one extra CSS custom property** per `data-theme` (e.g. `--product-chrome-accent`) used only in `brand-gradient` and hero components — *do not* fork component libraries per product.
4. **AxiomFolio-Next** — When migration allows, **import company neutrals** from `themes.css` *first*, then *layer* `axiomfolio.css` only for *finance* semantics (stage badges, series). Goal: *one spine, one overlay.*
5. **Rollout** — Prefer **`data-theme` + optional `data-brand="paperwork-labs-2026"`** attribute for staged rollouts, or a short-lived `NEXT_PUBLIC_PLABS_THEME=1` in preview — avoid big-bang without screenshot tests.
6. **QA** — For each app’s **top 3 routes**: run Lighthouse *accessibility*; Percy or Playwright screenshot diff **dark + light**; manual **focus ring** on primary buttons.

**Indicative effort**: **3–5 dev-days** for a careful engineer (including review and fixing contrast regressions) **after** design sign-off, **+2 days** for unexpected FileFree light-mode edge cases. **Not** a “afternoon in CSS” for a system this forked.

## 10. Decisions Sankalp needs to make (action items)

- **“Single palette (A) vs shared + accent (B)?”** — **Recommend B.** *Cost of A*: product marketing becomes harder; SEO thumbnails blur together.
- **“Keep literal gold, or nudge to ‘champagne’ / ‘wheat’ for 2026?”** — **Recommend** keeping gold **for AxiomFolio and hero moments**, but **codify a darker** companion for text on light. *Cost of switching the hue family*: one extra design review cycle, worth it if *crypto* connotations spook the board.
- **“Paperclip: commit or keep wordmark-only through 2026?”** — **Recommend** funding **3-direction exploration** (Sprint-sized), then decide. *Cost of skipping*: you save *design $* but pay *brand confusion* at every new product launch.
- **“Do we rebrand the consumer sites *before* or *after* AxiomFolio-Next migration?”** — **Recommend after** the Streamline+SSO spine is stable, per the sibling sprint. *Cost of doing it first*: *merge conflicts* and *split QA surface area*.
- **“Who owns tokens — Brand or Design Systems in Engineering?”** — **Recommend** a **lightweight “token council”** (brand + 1 eng + 1 PM) for **7 days** at kickoff, then *engineering owns* PRs with *brand* review on visual diffs only.

## 11. Open questions / next research

- **User testing** — Three palette directions (blue+gold, blue+violet, blue+teal) on **one** landing page and **one** in-app *happy path* with **≥10** paying or highly engaged users each — this doc *does not* replace qualitative preference data.
- **Trademark** — Paperclip shapes can collide with *Microsoft / generic office* cultural anchors; a *law* pass is out of scope here.
- **International** — Color psychology differs (gold as *festive* vs *gilded age*). If non-US is on the 24-month horizon, test **monochrome** logo acceptance first.
- **Accessibility audit** — A formal WCAG 2.2 audit of AxiomFolio (light) should happen **before** you declare the palette “company ready.”

## 12. Related

- [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc) — hierarchy, per-product copy, and palette tables (to be updated if this research is adopted).
- [`.cursor/rules/ux.mdc`](../../.cursor/rules/ux.mdc) — dark-first mobile, motion, accessibility baselines; any palette must satisfy these.
- [`packages/ui/src/themes.css`](../../packages/ui/src/themes.css) — shared `data-theme` HSL system (future edit surface).
- Per-app: [`apps/studio/src/app/globals.css`](../../apps/studio/src/app/globals.css), [`apps/filefree/src/app/globals.css`](../../apps/filefree/src/app/globals.css), [`apps/launchfree/src/app/globals.css`](../../apps/launchfree/src/app/globals.css), and AxiomFolio: [`apps/axiomfolio/src/index.css`](../../apps/axiomfolio/src/index.css), AxiomFolio-Next: [`apps/axiomfolio-next/src/app/axiomfolio.css`](../../apps/axiomfolio-next/src/app/axiomfolio.css), [`apps/axiomfolio-next/src/app/globals.css`](../../apps/axiomfolio-next/src/app/globals.css).
- Sibling sprint (foundation): [`STREAMLINE_SSO_DAGS_2026Q2.md`](STREAMLINE_SSO_DAGS_2026Q2.md).

---

*This document is **research** — it creates alignment and a dated snapshot of the codebase; it does not change product behavior.*
