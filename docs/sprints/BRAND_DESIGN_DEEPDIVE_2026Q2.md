---
title: Brand canon (2026 Q2)
owner: brand
last_reviewed: 2026-04-25
doc_kind: sprint
domain: company
status: decided
sprint:
  start: 2026-04-25
  end: 2026-05-16
  duration_weeks: ~3
related_prs:
  - "PR #162 (initial McKinsey-style framing — superseded)"
  - "PR #172 (this rewrite, pivoted to per-product palettes + AI-generated consumer marks)"
---

# Brand canon (2026 Q2)

**Purpose**: Lock the Paperwork-Labs-after-AxiomFolio brand architecture. AxiomFolio is no longer a separate company — it's a product inside Paperwork Labs. This doc settles the questions that fact creates: which palette is canon, how the marks coexist, what each product's logo is, and where Brain (the new B2C meta-product) sits.

**Status**: Decided. Sankalp owns the call; this is the call.

**Scope of this PR (#172)**: Brand-canon docs + parent paperclip mark + Studio mark + per-product palette lock + `docs/brand/PROMPTS.md` (AI image-generation prompts for the six consumer marks). **No theme migration code**, no app-level redirects, no SEO updates. **No consumer product SVGs** — those land in per-product follow-up PRs after the prompts are run externally.

## 1. Locked decisions

### 1.1 AxiomFolio's design system is the company baseline

AxiomFolio is the only surface in the repo with a mature, product-grade visual system: oklch token pipeline, semantic status colors, a color-blind chart palette (`data-palette="cb"`), and a real elevation scale. The other apps are coherent shadcn shells.

We don't average down to the lowest common denominator; we level up to the highest. **AxiomFolio's `apps/axiomfolio/src/index.css` is the de-facto company baseline.** When the engineering migration sprint lands, `packages/ui/src/themes.css` adopts AxiomFolio's token shape (oklch + semantic) wholesale, and per-app `globals.css` files become thin overlays.

### 1.2 Per-product primary hue (NOT all-azure-everything)

The 2026-04-25 first cut of this PR put every product mark on the same Azure body + Amber accent. That kills product differentiation — the whole point of having separate products is that they have separate identities. Reversed.

Each consumer product owns its primary hue inside the parent system:

| Product | Primary | Accent | Rationale |
| --- | --- | --- | --- |
| AxiomFolio | `#3274F0` Azure | `#F59E0B` Amber | Earned existing identity; finance product; user-designed |
| FileFree | `#0EA5A6` Teal | `#F59E0B` Amber | Clean filing; water-clear; calm utility |
| LaunchFree | `#F97357` Coral | `#0F172A` Slate | Energy; warmth; rocket-launch |
| Distill | `#B8643A` Copper | `#0F172A` Slate | Refinement; concentration; whiskey-like depth |
| Trinkets | `#C026D3` Magenta | `#F59E0B` Amber | Playful; multiple small tools; distinct |
| Brain | `#7C3AED` Violet | `#F59E0B` Amber | Intelligence; slightly mystical; consumer-friendly |
| Studio | `#3274F0` Azure | `#F59E0B` Amber | Internal admin; uses parent palette |
| Paperwork Labs (parent) | `#3274F0` Azure | `#F59E0B` Amber | Parent monogram; matches AxiomFolio for family read |

What stays unified across the family:

- Slate-night `#0F172A` surface (light: white). This is the chrome.
- Inter wordmark, 600 weight, `font-size: 62`, `letter-spacing: -0.5` for lockups.
- 4-rule visual grammar (see §3 below).
- Lockup viewBox `720×150`, icon viewBox `128×128`.

So the family read comes from **shared chrome + shared wordmark + shared geometry conventions**, not from clobbering hue. AxiomFolio reads as part of Paperwork Labs because the wordmark and surface match — not because every product clones AxiomFolio's blue.

### 1.3 Hand-author the parent + admin chrome only; AI-generate the consumer marks

The 2026-04-25 first cut also tried to hand-author six consumer marks geometrically. They came out reading as a homogeneous "azure rectangle with amber dot" family. Pulled.

The right division of labor:

- **Hand-authored SVG** (this PR): Paperwork Labs paperclip, Studio panes. Utility marks where mechanical geometry suffices.
- **AI-generated** (follow-up PRs): FileFree, LaunchFree, Distill, Trinkets, Brain candidates. Consumer-facing marks need character; flat-vector AI output (Nano Banana / Midjourney / DALL-E) followed by SVG retracing produces marks with personality, scoped by the locked palette and the prompt scaffold in [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md).

Workflow per consumer product:

1. Sankalp runs the locked prompt in his preferred image-gen tool.
2. Picks the cleanest output (1024×1024, transparent PNG).
3. Drops the image back to the agent.
4. Agent retraces as clean SVG, validates, generates light/dark lockups, opens a per-product follow-up PR.

One product per PR. Iterate without giant merges.

### 1.4 Brain is the consumer life-intelligence meta-product

Per `docs/BRAIN_ARCHITECTURE.md` D49 (Memory Moat), F90 (Brain Fill Meter), and G01 (the orbital knowledge-graph philosophy): Brain is no longer positioned as B2B agent-ops. It's a B2C product that subsumes other Paperwork Labs products as "skills." Tax-filing, LLC-formation, document-organization — all become things Brain knows how to do for you.

External product name and domain: **TBD pending availability research.** `paperwork.ai` is unavailable. Internal codename stays "Brain." Two glyph candidates land via PROMPTS.md:

- **A** — fill meter (vertical gauge, three context bars at increasing fill levels; tied to the Brain Fill Meter UX in F90).
- **B** — orbital arcs (three concentric arcs around a central self-node; tied to the orbital knowledge-graph philosophy).

Sankalp picks one after running both prompts. Loser archives.

### 1.5 Children's books = incidental publishing under PWL LLC

Sankalp wants to publish Hindi (and other-language) children's books on Amazon under the Paperwork Labs LLC umbrella, with AI-generated illustrations. This is **incidental publishing**, not a product line. Treatment:

- Imprint name: "Paperwork Labs LLC" appears **only on the copyright page** ("Published by Paperwork Labs LLC, California").
- Books carry **their own series brand** (e.g. a "Boond" series imprint or per-character branding) on the cover, spine, and marketing.
- No use of the paperclip mark, the Paperwork Labs wordmark, or the trinity palette on book interiors or covers.
- AI illustration is a hard constraint; no human-illustrator commissions in this venture.

A separate chat thread / planning doc covers the books venture. This PR codifies only the **brand attribution rule** so a stray AI search later doesn't sweep books into the company brand canon.

### 1.6 Marks delivered in PR #172

| Mark | Source | File |
| --- | --- | --- |
| Paperwork Labs paperclip (icon) | hand-authored, this PR | `apps/studio/public/brand/paperwork-labs-icon.svg` |
| Paperwork Labs lockup (light) | hand-authored, this PR | `apps/studio/public/brand/paperwork-labs-lockup.svg` |
| Paperwork Labs lockup (dark) | hand-authored, this PR | `apps/studio/public/brand/paperwork-labs-lockup-dark.svg` |
| Studio (window panes) | hand-authored, this PR | `apps/studio/public/brand/studio-icon.svg` |
| Studio lockup (light) | hand-authored, this PR | `apps/studio/public/brand/studio-lockup.svg` |
| Studio lockup (dark) | hand-authored, this PR | `apps/studio/public/brand/studio-lockup-dark.svg` |
| FileFree | **deferred — AI prompt** | per [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md), then per-product PR |
| LaunchFree | **deferred — AI prompt** | per [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md), then per-product PR |
| Distill | **deferred — AI prompt** | per [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md), then per-product PR |
| Trinkets | **deferred — AI prompt** | per [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md), then per-product PR |
| Brain candidate A (fill meter) | **deferred — AI prompt** | per [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md), then chosen-direction PR |
| Brain candidate B (orbital arcs) | **deferred — AI prompt** | per [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md), then chosen-direction PR |

See [`docs/brand/README.md`](../brand/README.md) for the live asset registry, visual grammar, and "do nots."

## 2. Why these decisions (one-paragraph each)

### Why AxiomFolio's system as baseline (not a new system)

We considered building a fresh "Paperwork Labs 2026" token system from scratch. Rejected: AxiomFolio already has the only working oklch pipeline, color-blind chart palette, and elevation scale in the repo. Building parallel would mean two systems competing, two QA surfaces, and a longer migration. Promoting AxiomFolio's system means **the highest-quality surface today becomes the standard tomorrow** — which is exactly what "we want to be the best" looks like in practice.

### Why per-product hue (not all-azure-everything)

The first attempt at this PR hand-authored six consumer marks all on Azure + Amber. They came out indistinguishable. The thinking was "unified family." The reality was "six clones." Each product is a distinct value proposition (file taxes / form a company / refine planning / collect tools / accumulate intelligence) and the icon must telegraph that distinction at favicon scale. Per-product hue with shared chrome is how this is solved across consumer-tech (think Notion, Linear, Vercel sub-brands) — same surface chrome, distinct primary hue. We adopt the same.

### Why hand-author parent only (not consumer marks)

Hand-authored geometric SVG works for utility marks where the metaphor is mechanical (a paperclip, a window grid). It does not produce the character a consumer-facing app icon needs. We tried; the output was competent geometry without personality. AI-generated flat-vector marks, scoped by a strict prompt scaffold (locked palette, locked style, no text/gradients/shadows), produce marks with character that we then retrace as clean SVG. This moves the creative bottleneck from "agent draws geometric shapes" to "agent writes good prompts and curates outputs," which is what agents are good at.

### Why trinity stays the chrome

Even though primary hues vary per product, the trinity (Azure + Amber + Slate-night) lives in: parent monogram, Studio admin chrome, Paperwork Labs lockup wordmark, the wordmark color used in every per-product lockup. It's the family thread. AxiomFolio's `#3274F0` and `#F59E0B` are promoted to family-trinity status because they were earned through actual product work, not invented for branding's sake.

### Why paperclip (and not abstract symbol)

We considered: (1) abstract continuous loop suggesting "infinity / always connected," (2) negative-space P inside a stylized form, (3) literal-but-cleaner paperclip. The user's brief mentioned paperclip explicitly; the metaphor is right (paperclip = the small tool that holds paperwork together = "Paperwork Labs"). The infinity loop reads crypto. Hidden-P is too clever for favicon size. Literal paperclip with continuous-wire vertical geometry is **direct, brand-safe, and recognizable at 16×16**. Office-suite-Clippy risk is real; mitigated by single-stroke modern execution + amber accent dot at the wire terminus.

### Why Brain pivots to B2C meta-product

`docs/BRAIN_ARCHITECTURE.md` and `docs/philosophy/BRAIN_PHILOSOPHY.md` describe Brain as a long-term memory and life-intelligence engine. The 2025 framing was "agent-ops platform for B2B." That framing under-monetizes the technology — every B2C product Paperwork Labs ships (FileFree, LaunchFree, AxiomFolio) already has Brain as its backend. Surfacing Brain to consumers as the **product whose skills are FileFree/LaunchFree/AxiomFolio** is the meta-product play. Naming and domain TBD; visual direction locked here via two glyph candidates.

## 3. Logo grammar (in 5 rules)

1. **128×128 viewBox** for icons, **720×150** for lockups.
2. **One amber accent dot** per glyph (or one slate accent on Coral / Copper marks where amber clashes). Always one. Never two. The dot is "the earned moment."
3. **Stroke or fill, not both** — pick one per glyph. Paperwork Labs paperclip is stroke-based. AxiomFolio's star is fill-based. Both are canon.
4. **No gradients, drop shadows, or filters** in the SVG file. Marketing surfaces add ambient effects in CSS at the layer above.
5. **Inter 600** at `font-size: 62`, `letter-spacing: -0.5` for lockup wordmarks. System stack fallback. No custom fonts.

These rules are also encoded in [`docs/brand/README.md`](../brand/README.md) and [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc). If you can't meet them, request a brand review before shipping the asset.

## 4. What's NOT in this PR (deferred follow-ups)

| Deferred | Why | When |
| --- | --- | --- |
| Theme migration code (move AxiomFolio's tokens into `packages/ui/src/themes.css`) | Big enough to deserve its own sprint with screenshot diffs | After current STREAMLINE_SSO_DAGS sprint closes (~2026-05-16) |
| Consumer product marks (FileFree / LaunchFree / Distill / Trinkets / Brain) | Need AI generation per [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md) and human curation | Per-product PRs as Sankalp runs prompts |
| Brain external name + domain | Domain availability sweep needed | Tracked separately; visual direction landed here so we don't block on naming |
| Consumer-site rebrands (FileFree, LaunchFree marketing pages adopt new palette) | Coordination cost across product/marketing | After theme migration sprint |
| Investor deck redesign | Brand work, not engineering | When deck is next due |
| Trademark sweep on paperclip mark | Legal review out of scope here | Separate task; flagged for follow-up |

## 5. AxiomFolio palette reference (kept as appendix)

The AxiomFolio mark uses `#3274F0` for petals and `#F59E0B` for the center dot. The full AxiomFolio token system in `apps/axiomfolio/src/index.css` covers ~310 lines of oklch + RGB semantic tokens including:

- Series palette `--series-1` through `--series-8` (lifted ~12% lightness for dark theme legibility).
- Color-blind palette `[data-palette="cb"]` using Okabe-Ito-inspired hues.
- Elevation scale `--shadow-resting` / `--shadow-hover` / `--shadow-active` / `--shadow-floating`.
- Status semantics `--status-success` / `--status-warning` / `--status-danger` / `--status-info`.
- Auth-page gradients `--auth-gradient-blue` / `--auth-gradient-amber` / `--auth-gradient-bg` / `--auth-gradient-glow`.
- Stage badges `--palette-stage-gray` through `--palette-stage-red` for portfolio rebalance UX.

This is what gets promoted to `packages/ui/src/themes.css` in the migration sprint.

## 6. Lessons from the first cut

The 2026-04-25 first cut got two things wrong; both reversed in this rewrite:

1. **Conflated "unified" with "homogeneous."** All-azure-everything looks unified at first glance and indistinguishable thirty seconds later. Family unity belongs in chrome + wordmark + grammar, not in primary hue.
2. **Tried to hand-author character.** Geometric SVG from agents floors at "competent." Consumer marks need character. The right split is hand-author the utility marks (parent, admin) and AI-generate the consumer marks with strict-palette prompts.

Both lessons should propagate to other "design system" sprints and should be referenced if anyone proposes a one-palette-fits-all approach again.

## 7. Related

- [`docs/brand/README.md`](../brand/README.md) — canonical SVG asset registry and grammar rules.
- [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md) — AI image-generation prompts per consumer product.
- [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc) — brand identity guide (always-active rule).
- `apps/axiomfolio/src/index.css` — AxiomFolio's oklch token system (the future baseline).
- `packages/ui/src/themes.css` — current shared HSL theme system (gets rewritten in migration sprint).
- `docs/BRAIN_ARCHITECTURE.md` — Brain as B2C meta-product (D49 / F90 / G01).
- `docs/philosophy/BRAIN_PHILOSOPHY.md` — orbital knowledge-graph philosophy (informs Brain glyph B).
- `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md` — sibling sprint that must close before theme migration begins.

---

*This document is **decided**, not advisory. If you're reading this and disagree, open a brand-review PR and present evidence — don't quietly drift.*
