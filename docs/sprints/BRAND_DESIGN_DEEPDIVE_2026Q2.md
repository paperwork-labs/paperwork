---
title: Brand canon (2026 Q2) — final
owner: brand
last_reviewed: 2026-04-26
doc_kind: sprint
domain: company
status: decided
sprint:
  start: 2026-04-25
  end: 2026-05-16
  duration_weeks: ~3
related_prs:
  - "PR #162 (McKinsey-style framing — superseded)"
  - "PR #172 (per-product palettes + droplet-family SVG locks + docs)"
---

# Brand canon (2026 Q2) — final state

**Purpose:** Lock Paperwork Labs’ post–AxiomFolio architecture: per-product **full palettes**, **organic similarity > forced unification**, a shared **droplet + dot** vocabulary for consumer marks (except Brain and the parent paperclip), and clear handoff to engineering (theme migration is a **separate** sprint).

**Status:** Decided. Founder approved research-locked picks and SVG sources 2026-04-26.

**Scope of PR #172 (evolved):** Brand rules, `docs/brand/*`, parent/Studio marks (interim hand where noted), **locked SVG icons** + **PNG renders** for FileFree, LaunchFree, Distill, Trinkets. **Not in scope:** merging `packages/ui/src/themes.css` to final per-app tokens (banner marks file as scaffolding); **not** merging; **not** swapping every in-app CTA without a theme sprint.

---

## 1. Family principle (replaces a single “one template for all” family thread)

**Organic similarity > forced unification.**

- **Similarity:** Inter wordmarks, shared 128×128 icon grammar, droplet-based marks that echo AxiomFolio’s 4-petal + center structure without copying it.
- **Not forced:** Same primary on every product, or a single “template” lockup inked identically on every brand. Those approaches were tried and **reversed** (see §5).

What **is** the family thread:

- Typography (Inter, same weight/spacing discipline).
- Geometry (viewBox, one accent per glyph, no gradients in repo SVGs).
- **Droplet + dot** vocabulary for FileFree, LaunchFree, Distill, Trinkets, and the AxiomFolio anchor.
- Legal line: “by Paperwork Labs” on product surfaces.

What is **not** the family thread:

- A single shared primary/accent across all products.
- **Organic similarity > forced unification** supersedes any earlier “same wordmark treatment / same parent colorway for everyone” rule — that rule homogenized marks in the second 2026-04-25 cut as badly as the first cut’s “all Azure + Amber.”

---

## 2. Research-locked picks (founder-approved 2026-04-26)

| Product | Mark | Primary | Accent | Research lock (one line) |
| --- | --- | --- | --- | --- |
| AxiomFolio | 4-petal droplet star (hand) | Azure `#3274F0` | Amber `#F59E0B` | Warriors-inspired blue/gold; company anchor; droplet vocabulary source. |
| FileFree | `ff-3B-invert.svg` → repo | Indigo `#4F46E5` | Lime `#84CC16` | vs TurboTax/H&R/Intuit green+blue massing; indigo+lime = modern + money-positive. |
| LaunchFree | `lf-lock-skycyan.svg` → repo | Sky `#0284C7` | Cyan `#06B6D4` | vs LegalZoom orange, ZenBusiness green, Stripe Atlas indigo; sky = literal launch. |
| Distill | `explore-distill-2C-yinyang.svg` → repo | Teal `#0F766E` | Burnt orange `#C2410C` | LibreTexts / standard still: vapor–condensate–essence; B2B lane must not mirror AxiomFolio azure. |
| Trinkets | `tk-pair-asym.svg` → repo | Indigo `#6366F1` | Sky cyan `#38BDF8` | Funnel sibling to FileFree (`tools.filefree.ai`); hue continuity > artificial split. |
| Brain | **No droplet** — AI brain | Emerald `#10B981` | Mint `#6EE7B7` | vs brain.ai/Mem/Reflect violet cluster; custody + growth, not “purple AI.” |
| Paperwork Labs | **No final SVG** — AI paperclip | Slate ink `#0F172A` | Amber `#F59E0B` | Gem-clip / attachment metaphor (Notion, Slack); one amber segment on slate — not Azure. |

**Studio** (not in founder table): inherits **Azure + Amber** with AxiomFolio — admin chrome, chain-of-life, not a separate consumer brand story.

---

## 3. Decision matrix (how we chose)

| Criterion | Weight | Outcome |
| --- | --- | --- |
| Category color maps (tax, formation, B2B tax-pro) | High | Counter-position vs match for free/modern wedge; **exception** Trinkets = match FileFree for funnel. |
| In-portfolio collision | High | Distill must not read as second AxiomFolio; Brain must not read as “another purple AI app.” |
| Compositional differentiation | High | First PR #172 cut: six Azure+Amber marks — **rejected**; second cut: forced identical lockup treatment — **rejected**; **droplet + dot** with varying counts = organic similarity. |
| Founder taste / execution | Final | AxiomFolio hand mark untouched; droplet alternates down-selected in `.brand-preview` contact sheets. |

---

## 4. Shipped files (this canon)

| Product | Icon path | Notes |
| --- | --- | --- |
| FileFree | `apps/filefree/public/brand/filefree-icon.svg` | 3 droplets + center dot |
| LaunchFree | `apps/launchfree/public/brand/launchfree-icon.svg` | Single droplet + cyan dot |
| Distill | `apps/distill/public/brand/distill-icon.svg` | Opposed droplets + center dot (yin–yang) |
| Trinkets | `apps/trinkets/public/brand/trinkets-icon.svg` | Asymmetric droplet pair + highlight dot |
| AxiomFolio | `apps/axiomfolio/src/assets/logos/axiomfolio-icon-star.svg` | Unchanged baseline |

**Rasters:** for each of the four promoted apps, `public/brand/renders/*-icon-{16,32,64,128,256,512,1024}.png` (sips from SVG).

**Interim (replace when AI parent ships):** `apps/studio/public/brand/paperwork-labs-*.svg`, Studio grid marks.

**Brain + parent:** see [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md) — `Emerald #10B981` / `Mint #6EE7B7` and slate+amber for parent prompts.

---

## 5. History of pivots (short)

1. **PR #162** — High-level brand framing; superseded by evidence-grounded per-product work.
2. **2026-04-25 first cut** — All marks on Azure + Amber; indistinguishable; **reverted**.
3. **2026-04-25 second cut** — “Same treatment on every lockup” (forced homogeneity); **reverted**; Sankalp: *“forced is the key word, organic similarities are beautiful.”* **Organic similarity > forced unification** is the named replacement for that *template-everywhere* rule.
4. **2026-04-25 five dives** — FileFree, LaunchFree, Distill, Trinkets, Brain: independent agent briefs; all favored **counter-positioning** in category; Trinkets explicitly matched FileFree for funnel.
5. **2026-04-26** — Founder locks final droplet SVGs from `.brand-preview` research; Brain palette set to **#10B981 / #6EE7B7**; parent mark stays **slate + amber** (not parent Azure).
6. **Engineering** — `packages/ui/src/themes.css` left as **scaffolding** until a dedicated theme-migration sprint re-homes tokens under `apps/{product}/…`.

---

## 6. Brain as B2C meta-product (unchanged strategy)

Per `docs/BRAIN_ARCHITECTURE.md` (D49, F90, G01): Brain is the B2C surface that other products join as **skills**. Naming/domain still **TBD**; **visual = brain glyph**, not droplets. Two orbital/fill exploration prompts are **optional** in [`PROMPTS.md`](../brand/PROMPTS.md) only if the primary brain line prompt is insufficient.

---

## 7. Children’s books (incidental)

Unchanged: imprint on copyright page only; no Paperwork Labs consumer palette on covers. See [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc).

---

## 8. Related docs

- [`docs/brand/README.md`](../brand/README.md) — asset registry + full palette table.
- [`docs/brand/PROMPTS.md`](../brand/PROMPTS.md) — LLM / image prompts with hexes embedded.
- [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc) — always-on rule.
- `apps/axiomfolio/src/index.css` — AxiomFolio token depth (oklch) — **shape** to follow in migration sprint, not universal hue.
- `packages/ui/src/themes.css` — **Scaffolding** until theme migration.

---

*This document is **decided**. To propose a change, open a brand-review PR with new evidence; do not silently drift marks or hexes.*
