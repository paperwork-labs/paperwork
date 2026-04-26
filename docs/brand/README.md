---
title: Paperwork Labs Brand Asset Registry
owner: brand
last_reviewed: 2026-04-25
doc_kind: reference
domain: company
---

# Paperwork Labs brand asset registry

Single source of truth for canonical SVG marks across Paperwork Labs and its products. If a logo or product glyph isn't listed here, it isn't canonical yet.

## Trinity palette (parent brand + B2B chrome)

| Token | Light surface | Dark surface | Role |
| --- | --- | --- | --- |
| Azure | `#3274F0` | `#60A5FA` | Primary structural mark |
| Amber | `#F59E0B` | `#FBBF24` | Earned accent (single dot per glyph) |
| Slate-night | `#0F172A` | `#FAFAFA` | Wordmark + body type |

These three colors define every Paperwork-Labs-and-Studio-and-Distill mark. Consumer products (FileFree, LaunchFree, Trinkets, AxiomFolio) keep their own primary CTA hue inside the product UI but use **the trinity** in their canonical SVG mark so the brand family reads at a glance in the browser tab strip.

## Visual grammar

All canonical marks share these constraints (intentional, do not deviate without a brand review):

1. **viewBox**: `0 0 128 128` for icons, `0 0 720 150` for lockups.
2. **Padding**: `~16px` of breathing room from viewBox edges to mark.
3. **Stroke width**: `9–11` for stroke-based glyphs (matches optical weight of AxiomFolio's filled petals).
4. **Caps + joins**: `round` everywhere a stroke terminates or bends.
5. **One amber accent per glyph.** Always one. Never two. The amber dot is the "earned moment" — never decorative.
6. **No drop shadows, gradients, or filters** in the canonical SVGs. Marketing surfaces may add ambient effects in CSS; the SVG file itself stays flat.
7. **Wordmark font**: Inter 600 with `letter-spacing: -0.5` at `font-size: 62`. Falls back through the system stack.

## Asset registry

### Paperwork Labs (parent brand)

| File | Use | Surface |
| --- | --- | --- |
| `apps/studio/public/brand/paperwork-labs-icon.svg` | Favicon, social avatar, app launcher icons | Any |
| `apps/studio/public/brand/paperwork-labs-lockup.svg` | Marketing site, investor decks, signed PDFs | Light |
| `apps/studio/public/brand/paperwork-labs-lockup-dark.svg` | Studio app, dark marketing pages | Dark |

The paperclip is the parent mark: a single azure stroke forming a paperclip silhouette with one amber accent dot at the inner-wire terminus.

### Studio

| File | Use | Surface |
| --- | --- | --- |
| `apps/studio/public/brand/studio-icon.svg` | Studio nav, internal admin tooling | Any |

Window-pane grid metaphor: the four panes represent the four operational surfaces (Operations, Personas, Workflows, Sprints). The amber pane is the active one.

### FileFree

| File | Use |
| --- | --- |
| `apps/filefree/public/brand/filefree-icon.svg` | App icon + favicon |

Folded document with an amber checkmark — "your return is filed."

### LaunchFree

| File | Use |
| --- | --- |
| `apps/launchfree/public/brand/launchfree-icon.svg` | App icon + favicon |

Stacked launch chevrons with an amber ignition dot at the tip.

### Distill

| File | Use |
| --- | --- |
| `apps/distill/public/brand/distill-icon.svg` | App icon + favicon |

Funnel with the refined-droplet (amber) emerging at the stem — the literal distillation metaphor.

### Trinkets

| File | Use |
| --- | --- |
| `apps/trinkets/public/brand/trinkets-icon.svg` | App icon + favicon |

Constellation of five azure utility nodes around a central amber node. Reads as "small things that work together."

### AxiomFolio (existing canon, untouched here)

| File | Use |
| --- | --- |
| `apps/axiomfolio/src/assets/logos/axiomfolio.svg` | App icon |
| `apps/axiomfolio/src/assets/logos/axiomfolio-icon-star.svg` | Star-form icon (4 petals + amber center) |
| `apps/axiomfolio/src/assets/logos/axiomfolio-lockup.svg` | Wordmark + icon |

AxiomFolio's mark is hand-authored and stays as-is. Its 4-petal-plus-amber-center geometry is the visual anchor that informed the trinity palette.

### Brain (candidate glyphs, awaiting selection)

Brain is the consumer life-intelligence meta-product (per `docs/BRAIN_ARCHITECTURE.md` D49 / F90 / G01). Its external product name and domain are **TBD pending availability research** — `paperwork.ai` is unavailable. Internal codename remains "Brain."

| File | Concept |
| --- | --- |
| `docs/brand/brain/brain-icon-fill-meter.svg` | Three context bars filling progressively inside a rounded container — the "brain fill meter" metaphor (D51) |
| `docs/brand/brain/brain-icon-orbital-dag.svg` | Three concentric arcs with a central self-node and one satellite — the orbital knowledge-graph metaphor |

Once Sankalp picks a glyph and the external name is confirmed, the chosen file moves to the product app's `public/brand/` directory and the unchosen file is deleted from this repo.

## Future variants (delegated, lands in this same PR)

Per-product lockup variants (icon + wordmark, light and dark surfaces) for FileFree, LaunchFree, Distill, Trinkets, and Studio are generated as a follow-up commit on this branch. The canonical icons above are the source — variants compose the icon at `(11, 11)` with a wordmark to the right at `x=160`.

## Adding a new mark

1. Author the SVG by hand (no AI generation tools — they introduce stroke inconsistency that breaks the visual grammar). Use 128×128 viewBox, the trinity palette, and one amber accent.
2. Validate XML: `xmllint --noout your-icon.svg`
3. Render preview: `qlmanage -t -s 256 -o /tmp your-icon.svg && open /tmp/your-icon.svg.png`
4. Add to the registry table above.
5. Update `.cursor/rules/brand.mdc` "Logo Assets" section with the new path.
6. Open a PR titled `docs(brand): add <mark>` and request brand review.

## Don'ts

- Do **not** add a second accent color (no double amber, no green checkmark, etc).
- Do **not** rotate, skew, recolor, or filter canonical marks in product UI. Use them as-is or use a designated variant.
- Do **not** put the gold dot on a CTA. The amber accent is reserved for canonical marks and earned moments (success states, completion confirmations). It is not a button color.
- Do **not** introduce per-product paperclip variations. The paperclip is the parent-only mark.
