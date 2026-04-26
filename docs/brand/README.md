---
title: Paperwork Labs Brand Asset Registry
owner: brand
last_reviewed: 2026-04-25
doc_kind: reference
domain: company
---

# Paperwork Labs brand asset registry

Single source of truth for canonical SVG marks across Paperwork Labs and its products. If a logo or product glyph isn't listed here, it isn't canonical yet.

See [`docs/sprints/BRAND_DESIGN_DEEPDIVE_2026Q2.md`](../sprints/BRAND_DESIGN_DEEPDIVE_2026Q2.md) for the brand canon decisions and rationale.

## Trinity (chrome — used in every mark)

| Token | Light surface | Dark surface | Role |
| --- | --- | --- | --- |
| Slate-night | `#0F172A` | `#FAFAFA` | Wordmark + body type, surface |
| Inter 600 wordmark | — | — | Family thread across all lockups |
| 5-rule visual grammar | — | — | Identical across all marks |

Family read comes from shared chrome + shared wordmark + shared geometry. **Not** from cloning hue.

## Per-product mark palette

Each consumer product owns its primary hue. This is what differentiates the marks at favicon scale.

| Product | Primary | Accent |
| --- | --- | --- |
| Paperwork Labs (parent) | Azure `#3274F0` | Amber `#F59E0B` |
| Studio (admin chrome) | Azure `#3274F0` | Amber `#F59E0B` |
| AxiomFolio | Azure `#3274F0` | Amber `#F59E0B` |
| FileFree | Teal `#0EA5A6` | Amber `#F59E0B` |
| LaunchFree | Coral `#F97357` | Slate `#0F172A` |
| Distill | Copper `#B8643A` | Slate `#0F172A` |
| Trinkets | Magenta `#C026D3` | Amber `#F59E0B` |
| Brain | Violet `#7C3AED` | Amber `#F59E0B` |

## Visual grammar

All canonical marks share these constraints (intentional, do not deviate without a brand review):

1. **viewBox**: `0 0 128 128` for icons, `0 0 720 150` for lockups.
2. **Padding**: `~16px` of breathing room from viewBox edges to mark.
3. **Stroke width**: `9–11` for stroke-based glyphs (matches optical weight of AxiomFolio's filled petals).
4. **Caps + joins**: `round` everywhere a stroke terminates or bends.
5. **One accent dot per glyph.** Always one. Never two. The accent is the "earned moment" — never decorative.
6. **No drop shadows, gradients, or filters** in the canonical SVGs. Marketing surfaces may add ambient effects in CSS; the SVG file itself stays flat.
7. **Wordmark font**: Inter 600 with `letter-spacing: -0.5` at `font-size: 62`. Falls back through the system stack.

## Asset registry

### Paperwork Labs (parent brand)

| File | Use | Surface |
| --- | --- | --- |
| `apps/studio/public/brand/paperwork-labs-icon.svg` | Favicon, social avatar, app launcher icons | Any |
| `apps/studio/public/brand/paperwork-labs-lockup.svg` | Marketing site, investor decks, signed PDFs | Light |
| `apps/studio/public/brand/paperwork-labs-lockup-dark.svg` | Studio app, dark marketing pages | Dark |

The paperclip is the parent mark: continuous azure wire forming a vertical paperclip silhouette with one amber accent dot at the inner-wire terminus.

### Studio

| File | Use | Surface |
| --- | --- | --- |
| `apps/studio/public/brand/studio-icon.svg` | Studio nav, internal admin tooling | Any |
| `apps/studio/public/brand/studio-lockup.svg` | Studio header lockup | Light |
| `apps/studio/public/brand/studio-lockup-dark.svg` | Studio header lockup, dark mode | Dark |

Window-pane grid metaphor: four panes represent the four operational surfaces (Operations, Personas, Workflows, Sprints). The amber pane is the active one. Studio is internal admin chrome — not user-facing — so it shares the parent palette.

### AxiomFolio (existing canon, untouched here)

| File | Use |
| --- | --- |
| `apps/axiomfolio/src/assets/logos/axiomfolio.svg` | App icon |
| `apps/axiomfolio/src/assets/logos/axiomfolio-icon-star.svg` | Star-form icon (4 petals + amber center) |
| `apps/axiomfolio/src/assets/logos/axiomfolio-lockup.svg` | Wordmark + icon |

AxiomFolio's mark is hand-authored and stays as-is. Its 4-petal-plus-amber-center geometry is the visual anchor that informed the trinity chrome.

### FileFree

| File | Status |
| --- | --- |
| `apps/filefree/public/brand/filefree-icon.svg` | **TBD** — generate via [`docs/brand/PROMPTS.md`](PROMPTS.md), then per-product follow-up PR |
| Lockups (light + dark) | TBD — produced after icon lands |

Locked palette: Teal `#0EA5A6` + Amber `#F59E0B`. Metaphor: folded document + checkmark. See PROMPTS.md for the AI prompt.

### LaunchFree

| File | Status |
| --- | --- |
| `apps/launchfree/public/brand/launchfree-icon.svg` | **TBD** — generate via [`docs/brand/PROMPTS.md`](PROMPTS.md), then per-product follow-up PR |
| Lockups (light + dark) | TBD — produced after icon lands |

Locked palette: Coral `#F97357` + Slate accent. Metaphor: upward chevrons / rocket motion. See PROMPTS.md.

### Distill

| File | Status |
| --- | --- |
| `apps/distill/public/brand/distill-icon.svg` | **TBD** — generate via [`docs/brand/PROMPTS.md`](PROMPTS.md), then per-product follow-up PR |
| Lockups (light + dark) | TBD — produced after icon lands |

Locked palette: Copper `#B8643A` + Slate accent. Metaphor: funnel + droplet. See PROMPTS.md.

### Trinkets

| File | Status |
| --- | --- |
| `apps/trinkets/public/brand/trinkets-icon.svg` | **TBD** — generate via [`docs/brand/PROMPTS.md`](PROMPTS.md), then per-product follow-up PR |
| Lockups (light + dark) | TBD — produced after icon lands |

Locked palette: Magenta `#C026D3` + Amber accent. Metaphor: constellation / toolkit cluster. See PROMPTS.md.

### Brain (consumer meta-product, two glyph candidates)

Brain is the consumer life-intelligence meta-product (per `docs/BRAIN_ARCHITECTURE.md` D49 / F90 / G01). Its external product name and domain are **TBD pending availability research** — `paperwork.ai` is unavailable. Internal codename remains "Brain."

| Candidate | Concept | Status |
| --- | --- | --- |
| Fill meter | Three context bars filling progressively inside a rounded container — the brain fill meter metaphor (D51 / F90) | **TBD** — generate via [`docs/brand/PROMPTS.md`](PROMPTS.md) |
| Orbital arcs | Three concentric arcs with a central self-node and one satellite — orbital knowledge-graph metaphor (BRAIN_PHILOSOPHY.md) | **TBD** — generate via [`docs/brand/PROMPTS.md`](PROMPTS.md) |

Locked palette: Violet `#7C3AED` + Amber `#F59E0B`. Run both prompts; Sankalp picks one; chosen file moves to the product app's `public/brand/` directory in the per-product PR.

## Adding a new consumer mark (workflow)

1. Open [`docs/brand/PROMPTS.md`](PROMPTS.md) and find the locked prompt for the product.
2. Run the prompt in Nano Banana, Midjourney v6+, DALL-E 3, or Imagen. First round + 1 retry usually works.
3. Pick the cleanest output (1024×1024, transparent PNG).
4. Drop the image back to the agent.
5. Agent retraces the SVG manually, validates with `xmllint`, generates light/dark lockups, drops into `apps/<product>/public/brand/`, regenerates this registry, and opens a per-product follow-up PR.
6. One product per PR.

## Adding a new utility mark (parent chrome / admin)

For utility marks (not consumer-facing), hand-author by SVG:

1. Author the SVG by hand. Use 128×128 viewBox, the locked product palette, and one accent dot per the visual grammar.
2. Validate XML: `xmllint --noout your-icon.svg`
3. Render preview: `qlmanage -t -s 256 -o /tmp your-icon.svg && open /tmp/your-icon.svg.png`
4. Add to the registry table above.
5. Update [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc) Logo Assets section with the new path.
6. Open a PR titled `docs(brand): add <mark>` and request brand review.

## Don'ts

- Do **not** put consumer marks on a different palette than locked above. The palette IS the differentiator; collapsing it kills the family read of "different products inside one company."
- Do **not** add a second accent color per glyph (no double amber, no extra slate).
- Do **not** rotate, skew, recolor, or filter canonical marks in product UI. Use them as-is or use a designated variant.
- Do **not** put the accent dot on a CTA. It is reserved for canonical marks and earned moments (success states, completion confirmations).
- Do **not** put the paperclip mark on a product page — it's parent-only. Each product uses its own glyph.
- Do **not** hand-author consumer marks geometrically. The first cut of PR #172 tried this; the marks read as identical clones. Use [`docs/brand/PROMPTS.md`](PROMPTS.md).
