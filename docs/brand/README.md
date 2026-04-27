---
title: Paperwork Labs Brand Asset Registry
owner: brand
last_reviewed: 2026-04-26
doc_kind: reference
domain: company
---

# Paperwork Labs brand asset registry

Single source of truth for canonical SVG marks across Paperwork Labs and its products. If a logo or product glyph is not listed here, treat it as non-canonical or interim.

See [`docs/sprints/BRAND_DESIGN_DEEPDIVE_2026Q2.md`](../sprints/BRAND_DESIGN_DEEPDIVE_2026Q2.md) for the full history: research dives, decision matrix, founder locks (2026-04-26), and pivots away from "one template for every product."

## Family principle

**Organic similarity > forced unification.** Products share a **droplet + dot** visual vocabulary (count, layout, and color vary); they do not share one silhouette or one parent hue. What *does* align across the portfolio: Inter wordmarks, shared viewBox/grammar rules, surface-aware ink, and the legal "by Paperwork Labs" line.

**Not** the family thread: a single parent colorway cloned onto every app, or identical wordmark ink on every lockup.

## Per-product full palette (canonical)

Each row is the lock for marks, social templates, and (after the theme-migration sprint) product UI. **Primary** and **accent** are fixed for the glyph; **ink** shifts with light vs dark surface.

| Product | Primary | Accent | Neutral light | Neutral dark | Ink (on light) | Ink (on dark) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Paperwork Labs (parent) | Slate ink `#0F172A` | Amber `#F59E0B` | `#F8FAFC` | `#0F172A` | `#0F172A` | `#F8FAFC` | Parent *mark* is AI paperclip (slate + one amber span). Not Azure. |
| Studio | Azure `#3274F0` | Amber `#F59E0B` | `#F8FAFC` | `#0F172A` | `#0F172A` | `#F8FAFC` | Admin chrome; chain-of-life with AxiomFolio. |
| AxiomFolio | Azure `#3274F0` | Amber `#F59E0B` | `#F8FAFC` | `#0F172A` | `#0F172A` | `#F8FAFC` | Hand-designed 4-petal + center dot — family anchor. |
| FileFree | Indigo `#4F46E5` | Lime `#84CC16` | `#F8FAFC` | `#020817` / `#0F172A` | `#0F172A` | `#F8FAFC` | Locked SVG: three droplets converging on a dot. |
| LaunchFree | Sky `#0284C7` | Cyan `#06B6D4` | `#F8FAFC` | `#0A0F1A` / `#0F172A` | `#0C4A6E` | `#F8FAFC` | Locked SVG: one droplet + cyan dot below. |
| Distill | Teal `#0F766E` | Burnt orange `#C2410C` | off-white / `#F8FAFC` | `#0F172A` | `#115E59` | `#F8FAFC` | B2B default surface tends light. Locked SVG: opposing droplets + center dot. |
| Trinkets | Indigo `#6366F1` | Sky cyan `#38BDF8` | `#F8FAFC` | `#0C0A09` / `#0F172A` | `#1E1B4B` | `#F8FAFC` | Sibling to FileFree; locked SVG: asymmetric droplet pair + dot. |
| Brain | Emerald `#10B981` | Mint `#6EE7B7` | `#F8FAFC` | `#0F172A` | `#0F172A` | `#F8FAFC` | **No droplet mark** — AI brain glyph; see [`PROMPTS.md`](PROMPTS.md). |

**Primary on dark** (lighter strokes for lockups on dark fields): Axiom/Studio/PWL Azure → `#60A5FA` where applicable; FileFree indigo → `#818CF8`; LaunchFree sky → `#38BDF8`; Distill teal → `#14B8A6`; Trinkets indigo → `#A5B4FC`; Brain emerald → `#34D399`. **Accents** on dark: amber `#FBBF24`, lime `#A3E635`, cyan `#22D3EE`, burnt orange `#F97316`, sky cyan `#7DD3FC`, mint → `#A7F3D0` alongside mint `#6EE7B7` on the mark.

## Visual grammar (canonical marks)

1. **viewBox**: `0 0 128 128` for icons, `0 0 720 150` for lockups.
2. **Padding**: `~16px` breathing room from the viewBox edge.
3. **Stroke width**: `9–11` for stroke-based marks; round caps and joins; filled droplets may use fill (AxiomFolio star, FileFree family).
4. **One accent per glyph** — one earned moment, not two.
5. **No drop shadows, gradients, or filters** in repo SVGs; CSS may add sheen in marketing.
6. **Wordmark** (where present): Inter 600, `letter-spacing: -0.5`, `font-size: 62`.
7. **Droplet family thread**: derived from the AxiomFolio four-petal + dot vocabulary; each consumer mark varies count and composition.

## Asset registry (paths)

### Paperwork Labs (parent)

| File | Use | Note |
| --- | --- | --- |
| *Future:* AI paperclip from [`PROMPTS.md`](PROMPTS.md) | Favicon, avatar | Replaces interim assets when ready. |
| `apps/studio/public/brand/paperwork-labs/icon.svg` | Favicon, launcher | **Interim** hand mark. |
| `apps/studio/public/brand/paperwork-labs/lockup.svg` | Light surfaces | **Interim** lockup. |
| `apps/studio/public/brand/paperwork-labs/lockup-dark.svg` | Dark surfaces | **Interim** lockup. |
| `apps/studio/public/brand/paperwork-labs/paperclip/mark-diagonal.svg` | P1 diagonal mark | Parent paperclip (expressive default). |
| `apps/studio/public/brand/paperwork-labs/paperclip/mark-vertical.svg` | P2 vertical mark | Canonical parent icon / multi-app favicon source. |
| `apps/studio/public/brand/paperwork-labs/paperclip/clipped-wordmark.svg` | P5 clipped wordmark | Clip + "Paperwork Labs" wordmark. |

### Studio

| File | Use |
| --- | --- |
| `apps/studio/public/brand/studio-icon.svg` | Admin nav, tooling |
| `apps/studio/public/brand/studio-lockup.svg` | Light header |
| `apps/studio/public/brand/studio-lockup-dark.svg` | Dark header |

### AxiomFolio (locked — do not restyle)

| File | Use |
| --- | --- |
| `apps/axiomfolio/src/assets/logos/axiomfolio.svg` | Legacy app icon (prefer star) |
| `apps/axiomfolio/src/assets/logos/axiomfolio-icon-star.svg` | **Canonical** 128×128 star / favicon source |
| `apps/axiomfolio/src/assets/logos/axiomfolio-lockup.svg` | Wordmark + mark |

### FileFree

| File | Use |
| --- | --- |
| `apps/filefree/public/brand/filefree-icon.svg` | **Locked** mark — 3 droplets + center dot |
| `apps/filefree/public/brand/renders/filefree-icon-{16…1024}.png` | Raster previews / OG templates |

### LaunchFree

| File | Use |
| --- | --- |
| `apps/launchfree/public/brand/launchfree-icon.svg` | **Locked** mark — droplet + cyan dot |
| `apps/launchfree/public/brand/renders/launchfree-icon-{16…1024}.png` | Rasters |

### Distill

| File | Use |
| --- | --- |
| `apps/distill/public/brand/distill-icon.svg` | **Locked** mark — yin/yang droplets + center dot |
| `apps/distill/public/brand/renders/distill-icon-{16…1024}.png` | Rasters |

### Trinkets

| File | Use |
| --- | --- |
| `apps/trinkets/public/brand/trinkets-icon.svg` | **Locked** mark — asymmetric droplets + cyan dot |
| `apps/trinkets/public/brand/renders/trinkets-icon-{16…1024}.png` | Rasters |

### Brain

No shipped SVG in-repo yet. **Locked palette** Emerald `#10B981` + Mint `#6EE7B7`. Generation prompts: [`PROMPTS.md`](PROMPTS.md) (Brain + meta-product section).

## Workflows

### Adding a lockup after an icon exists

1. Use the **Ink** and **primary** columns from the table above.
2. `720×150` viewBox, Inter 600, no extra accent beyond the product rule.
3. `xmllint --noout` on every SVG; place next to the icon in `public/brand/`.

### Don’ts

- Do not put the **parent paperclip** on a consumer product page.
- Do not recolor a locked mark for "fun" A/B tests — ship a brand review if change is required.
- Do not add a second accent color in the same glyph.

## Related

- [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc) — always-on rule.
- [`PROMPTS.md`](PROMPTS.md) — LLM / image prompts with palettes baked in.
