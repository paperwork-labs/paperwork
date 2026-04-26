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
  - "PR #162 (initial McKinsey-style framing — superseded by this rewrite)"
---

# Brand canon (2026 Q2)

**Purpose**: Lock the Paperwork-Labs-after-AxiomFolio brand architecture. AxiomFolio is no longer a separate company — it's a product inside Paperwork Labs. This doc settles the questions that fact creates: which palette is canon, how the marks coexist, what each product's logo is, and where Brain (the new B2C meta-product) sits.

**Status**: Decided. Sankalp owns the call; this is the call. The McKinsey-style "should we unify?" framing in the original PR #162 was wrong-shaped — coexistence isn't optional. This rewrite ships the answers, not the debate.

**Scope of this PR**: Brand-canon docs + 9 hand-authored SVG marks + `.cursor/rules/brand.mdc` rewrite. **No theme migration code**, no app-level redirects, no SEO updates. Engineering migration is a follow-up sprint.

## 1. Locked decisions

### 1.1 AxiomFolio's design system is the company baseline

AxiomFolio is the only surface in the repo with a mature, product-grade visual system: oklch token pipeline, semantic status colors, a color-blind chart palette (`data-palette="cb"`), and a real elevation scale. The other apps are coherent shadcn shells.

We don't average down to the lowest common denominator; we level up to the highest. **AxiomFolio's `apps/axiomfolio/src/index.css` is the de-facto company baseline.** When the engineering migration sprint lands, `packages/ui/src/themes.css` adopts AxiomFolio's token shape (oklch + semantic) wholesale, and per-app `globals.css` files become thin overlays.

### 1.2 Trinity palette: Azure + Amber + Slate-night

Three colors define every Paperwork-Labs-and-Studio-and-Distill canonical mark:

| Token | Light surface | Dark surface | Role |
| --- | --- | --- | --- |
| Azure | `#3274F0` | `#60A5FA` | Primary structural mark |
| Amber | `#F59E0B` | `#FBBF24` | Earned accent (single dot per glyph) |
| Slate-night | `#0F172A` | `#FAFAFA` | Wordmark + body type |

The hex values come from AxiomFolio's existing logo (`#3274F0` is the petal blue, `#F59E0B` is the center dot) — the user designed those for AxiomFolio's Warriors-inspired palette and 3-year-old-blue-and-yellow vibe; we promote them to the company family.

### 1.3 Consumer products keep their primary CTA hue

In product UI, FileFree stays violet (`#4F46E5`), LaunchFree stays teal (`#0D9488`), Trinkets stays amber/orange (`#F59E0B` → `#EA580C`). Distill stays azure (it was always near `#2563EB` — close enough that we collapse to canonical `#3274F0`). Studio stays zinc-neutral.

This is "shared base + per-product CTA" — the repo's existing `data-theme` system. We don't squash it.

But: **canonical SVG marks all use the trinity.** Browser tab strips, social cards, and OG images need to read as a brand family at a glance. The CTA hue lives inside the product, not in the favicon.

### 1.4 Brain is the consumer life-intelligence meta-product

Per `docs/BRAIN_ARCHITECTURE.md` D49 (Memory Moat), F90 (Brain Fill Meter), and G01 (the orbital knowledge-graph philosophy): Brain is no longer positioned as B2B agent-ops. It's a B2C product that subsumes other Paperwork Labs products as "skills." Tax-filing, LLC-formation, document-organization — all become things Brain knows how to do for you.

External product name and domain: **TBD pending availability research.** `paperwork.ai` is unavailable. Internal codename stays "Brain." This PR ships two glyph candidates so visual direction is locked even before the name lands:

- `docs/brand/brain/brain-icon-fill-meter.svg` — three context bars filling progressively (the "fill meter" UX metaphor in F90).
- `docs/brand/brain/brain-icon-orbital-dag.svg` — three concentric arcs around a central self-node (the philosophical "knowledge orbits the user" metaphor).

Sankalp picks one. Loser gets deleted in a follow-up commit.

### 1.5 Children's books = incidental publishing under PWL LLC

Sankalp wants to publish Hindi (and other-language) children's books on Amazon under the Paperwork Labs LLC umbrella, with AI-generated illustrations. This is **incidental publishing**, not a product line. Treatment:

- Imprint name: "Paperwork Labs LLC" appears **only on the copyright page** ("Published by Paperwork Labs LLC, California").
- Books carry **their own series brand** (e.g. a "Boond" series imprint or per-character branding) on the cover, spine, and marketing.
- No use of the paperclip mark, the Paperwork Labs wordmark, or the trinity palette on book interiors or covers.
- AI illustration is a hard constraint; no human-illustrator commissions in this venture.

A separate chat thread / planning doc covers the books venture. This PR codifies only the **brand attribution rule** so a stray AI search later doesn't sweep books into the company brand canon.

### 1.6 9 SVG marks are delivered in this PR

Hand-authored, deliberately constrained, with one amber accent dot each:

| Mark | File |
| --- | --- |
| Paperwork Labs paperclip (icon) | `apps/studio/public/brand/paperwork-labs-icon.svg` |
| Paperwork Labs lockup (light) | `apps/studio/public/brand/paperwork-labs-lockup.svg` |
| Paperwork Labs lockup (dark) | `apps/studio/public/brand/paperwork-labs-lockup-dark.svg` |
| Studio (window panes) | `apps/studio/public/brand/studio-icon.svg` |
| FileFree (folded doc + check) | `apps/filefree/public/brand/filefree-icon.svg` |
| LaunchFree (chevrons + spark) | `apps/launchfree/public/brand/launchfree-icon.svg` |
| Distill (funnel + drop) | `apps/distill/public/brand/distill-icon.svg` |
| Trinkets (constellation) | `apps/trinkets/public/brand/trinkets-icon.svg` |
| Brain candidate A (fill meter) | `docs/brand/brain/brain-icon-fill-meter.svg` |
| Brain candidate B (orbital arcs) | `docs/brand/brain/brain-icon-orbital-dag.svg` |

Per-product lockup variants (icon + wordmark, light + dark) are generated as a follow-up commit on this branch by a delegated subagent. The canonical icons above are the source.

See `docs/brand/README.md` for the complete asset registry, visual grammar, and "do nots."

## 2. Why these decisions (one-paragraph each)

### Why AxiomFolio's system as baseline (not a new system)

We considered building a fresh "Paperwork Labs 2026" token system from scratch. Rejected: AxiomFolio already has the only working oklch pipeline, color-blind chart palette, and elevation scale in the repo. Building parallel would mean two systems competing, two QA surfaces, and a longer migration. Promoting AxiomFolio's system means **the highest-quality surface today becomes the standard tomorrow** — which is exactly what "we want to be the best" looks like in practice.

### Why trinity (azure + amber + slate-night) and not just blue

We considered single-blue institutional (Stripe-purple-style restraint) and we considered preserving AxiomFolio's full 8-token series palette. Rejected both. Single-blue gives up the AxiomFolio gold, which is half the brand's distinctive feature; full 8-series is too many decisions per screen. Trinity is **memorable at favicon size, scalable to 8-series in product, and the gold has a defined rare-and-earned role** so it never looks cheap.

### Why consumer products keep their CTA hue (and not full theme)

We considered three options: (A) one palette everywhere, (B) full per-product theming including chrome, (C) shared chrome + per-product CTA. We picked (C). (A) blurs categories and kills marketing differentiation. (B) is what we have today and it's fine but means investor decks look like 4 different companies. (C) — the repo's actual pattern — preserves SEO/marketing identity while signaling brand family in browser tabs and social cards.

### Why paperclip (and not abstract symbol)

We considered: (1) abstract continuous loop suggesting "infinity / always connected," (2) negative-space P inside a stylized form, (3) literal-but-cleaner paperclip. The user's brief mentioned paperclip explicitly; the metaphor is right (paperclip = the small tool that holds paperwork together = "Paperwork Labs"). The infinity loop reads crypto. Hidden-P is too clever for favicon size. Literal paperclip with deliberate stroke geometry is **direct, brand-safe, and recognizable at 16×16**. Office-suite-Clippy risk is real but mitigated by single-stroke modern execution + amber accent dot.

### Why Brain pivots to B2C meta-product

`docs/BRAIN_ARCHITECTURE.md` and `docs/philosophy/BRAIN_PHILOSOPHY.md` describe Brain as a long-term memory and life-intelligence engine. The 2025 framing was "agent-ops platform for B2B." That framing under-monetizes the technology — every B2C product Paperwork Labs ships (FileFree, LaunchFree, AxiomFolio) already has Brain as its backend. Surfacing Brain to consumers as the **product whose skills are FileFree/LaunchFree/AxiomFolio** is the meta-product play. Naming and domain are TBD; visual direction is locked here.

## 3. Logo grammar (in 5 rules)

1. **128×128 viewBox** for icons, **720×150** for lockups.
2. **One amber accent dot** per glyph. Always one. Never two. The dot is "the earned moment."
3. **Stroke or fill, not both** — pick one per glyph. Paperwork Labs paperclip is stroke-based. AxiomFolio's star is fill-based. Both are canon.
4. **No gradients, drop shadows, or filters** in the SVG file. Marketing surfaces add ambient effects in CSS at the layer above.
5. **Inter 600** at `font-size: 62`, `letter-spacing: -0.5` for lockup wordmarks. System stack fallback. No custom fonts.

These rules are also encoded in `docs/brand/README.md` and `.cursor/rules/brand.mdc`. If you can't meet them, request a brand review before shipping the asset.

## 4. What's NOT in this PR (deferred follow-ups)

| Deferred | Why | When |
| --- | --- | --- |
| Theme migration code (move AxiomFolio's tokens into `packages/ui/src/themes.css`) | Big enough to deserve its own sprint with screenshot diffs | After current STREAMLINE_SSO_DAGS sprint closes (~2026-05-16) |
| Per-product lockup variants (icon+wordmark for each product, light+dark) | Mechanical work; delegated to composer-2-fast as a follow-up commit on this branch | This PR (commit 2) |
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

## 6. Related

- `docs/brand/README.md` — canonical SVG asset registry and grammar rules.
- `.cursor/rules/brand.mdc` — brand identity guide (always-active rule).
- `apps/axiomfolio/src/index.css` — AxiomFolio's oklch token system (the future baseline).
- `packages/ui/src/themes.css` — current shared HSL theme system (gets rewritten in migration sprint).
- `docs/BRAIN_ARCHITECTURE.md` — Brain as B2C meta-product (D49 / F90 / G01).
- `docs/philosophy/BRAIN_PHILOSOPHY.md` — orbital knowledge-graph philosophy (informs Brain glyph B).
- `docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md` — sibling sprint that must close before theme migration begins.

---

*This document is **decided**, not advisory. If you're reading this and disagree, open a brand-review PR and present evidence — don't quietly drift.*
