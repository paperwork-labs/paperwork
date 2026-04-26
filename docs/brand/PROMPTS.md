---
title: Brand prompts — AI image-generation prompts per consumer product
owner: Paperwork Labs
last_reviewed: 2026-04-25
status: active
---

# Brand prompts

Per-product AI image-generation prompts for the six consumer marks that we deferred from PR #172. Run any of these in Nano Banana, Midjourney v6+, DALL-E 3, or Imagen, then drop the chosen image back so we can retrace it as a clean SVG and land it in a per-product follow-up PR.

## Why this exists

Hand-authored geometric SVG works for utility marks (Paperwork Labs paperclip, Studio admin grid) where the metaphor is mechanical. It does not produce the character that consumer-facing app icons need. The 2026-04-25 cut of PR #172 attempted six product icons and they all read as "azure rectangle with amber dot" — same composition, no differentiation. We pulled them.

This doc replaces them. Each product gets a locked palette, a metaphor brief, and a strict prompt format that constrains the model toward flat-vector geometry suitable for SVG retracing.

## Locked palette per product

Defined in [BRAND_DESIGN_DEEPDIVE_2026Q2.md](../sprints/BRAND_DESIGN_DEEPDIVE_2026Q2.md). Reproduced for prompt copy-paste convenience:

| Product | Primary | Accent | Surface (dark) |
| --- | --- | --- | --- |
| AxiomFolio | `#3274F0` Azure | `#F59E0B` Amber | `#0F172A` Slate-night |
| FileFree | `#0EA5A6` Teal | `#F59E0B` Amber | `#0F172A` |
| LaunchFree | `#F97357` Coral | `#0F172A` Slate | `#0F172A` |
| Distill | `#B8643A` Copper | `#0F172A` Slate | `#0F172A` |
| Trinkets | `#C026D3` Magenta | `#F59E0B` Amber | `#0F172A` |
| Brain | `#7C3AED` Violet | `#F59E0B` Amber | `#0F172A` |

## Universal prompt scaffold

All product prompts share this scaffold. Substitute the product-specific lines below.

> **A clean modern flat vector app icon for "{PRODUCT}". Centered subject: {METAPHOR}. Strict palette: primary {PRIMARY_HEX} ({PRIMARY_NAME}), single {ACCENT_HEX} ({ACCENT_NAME}) accent dot or short stroke detail. Transparent square canvas, app-icon proportions (subject fills ~60% of canvas). Geometric, minimal, rounded line caps and joins. Style reference: Linear, Vercel, Notion, Lucide, Phosphor app icons. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO photograph backgrounds, NO 3D rendering, NO skeuomorphism. Single coherent shape preferred. Confident, professional.**

Format requirements (state explicitly to the model):

- 1024×1024
- Transparent or pure white background
- Subject centered
- Easy to retrace as SVG (no fine detail, no gradients, no anti-aliased edges that aren't part of the geometry)

Iteration prompts that work:

- "Less skeuomorphic, more abstract"
- "Thicker strokes, more confident"
- "Single continuous shape if possible"
- "Reduce decorative elements; one accent only"
- "More upright/centered"

---

## FileFree — Teal `#0EA5A6` + Amber accent

**Product**: tax filer for self-filers. Files for free, hands you the IRS PDF. Hero promise: "filing taxes, finally easy."

**Metaphor candidates** (pick one or let the model interpret):

1. Stylized folded paper document with a confident checkmark inside.
2. Paper airplane folded from a tax form (motion + completion).
3. Open envelope with a single tick mark (sent, done).
4. Stack of three forms with the top one bearing a checkmark.

**Prompt**:

> A clean modern flat vector app icon for "FileFree" — a self-file tax app. Centered subject: a stylized folded paper document with one bold confident checkmark inside, geometric lines, rounded corners. Strict palette: primary teal #0EA5A6, single amber #F59E0B accent (the checkmark or a small dot). Transparent square canvas, app-icon proportions. Geometric, minimal, rounded line caps and joins. Style reference: Linear, Vercel, Notion app icons. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO 3D rendering, NO skeuomorphism. Single coherent shape preferred. Confident, slightly playful, professional.

---

## LaunchFree — Coral `#F97357` + Slate accent

**Product**: incorporation in a click. Spin up an LLC/C-corp without lawyers. Hero promise: "company, live in minutes."

**Metaphor candidates**:

1. Upward-pointing chevron stack (motion + ascent).
2. Stylized rocket silhouette (cliché but works if abstract enough).
3. Single bold upward arrow with an ignition spark at the base.
4. A blooming geometric flower — petals as upward-radiating shapes (more abstract, brand-distinct).

**Prompt**:

> A clean modern flat vector app icon for "LaunchFree" — an instant company-formation app. Centered subject: stacked upward chevrons or a single confident upward arrow with a small ignition mark at the base, conveying ascent and momentum. Strict palette: primary coral #F97357, single slate #0F172A accent dot or short detail. Transparent square canvas, app-icon proportions. Geometric, minimal, rounded line caps and joins. Style reference: Linear, Vercel, Lucide rocket and trending-up icons. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO 3D, NO skeuomorphism. Single coherent shape preferred. Confident, energetic, professional.

---

## Distill — Copper `#B8643A` + Slate accent

**Product**: tax planning intelligence. Distill turns financial chaos into tax-optimized moves. Hero promise: "your finances, refined."

**Metaphor candidates**:

1. Stylized funnel narrowing to a single droplet.
2. A flask or distillation vessel with a single concentrated drop emerging.
3. Two stacked triangles (one inverted) forming an hourglass-like shape — the act of refinement.
4. A spiral that tightens to a point — concentration.

**Prompt**:

> A clean modern flat vector app icon for "Distill" — a tax-planning intelligence app that refines financial complexity into clear moves. Centered subject: a stylized funnel narrowing to a single droplet at its base, OR a minimal flask silhouette with one concentrated drop. Strict palette: primary copper #B8643A, single slate #0F172A accent (the droplet itself or a small stem detail). Transparent square canvas, app-icon proportions. Geometric, minimal, rounded line caps and joins. Style reference: Lucide funnel and beaker icons, Linear's geometric simplicity. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO 3D, NO skeuomorphism, NO whiskey-glass cliches. Single coherent shape preferred. Refined, confident, slightly indulgent.

---

## Trinkets — Magenta `#C026D3` + Amber accent

**Product**: collection of small useful tax/finance tools. Hero promise: "the small tools that compound."

**Metaphor candidates**:

1. Constellation of 4-5 connected nodes forming an abstract cluster.
2. A swiss-army-knife silhouette, abstracted (multiple tools radiating from a center).
3. Four small geometric shapes (circle, square, triangle, hexagon) arranged in a 2×2 grid — the toolkit.
4. A single stylized gem or facet (the "trinket" itself, valuable + small).

**Prompt**:

> A clean modern flat vector app icon for "Trinkets" — a collection of small useful tax and finance utilities. Centered subject: a constellation of 4-5 small geometric nodes connected by thin lines, forming an abstract toolkit cluster, OR four distinct small geometric shapes (circle/square/triangle/hexagon) arranged playfully in a 2×2 grid. Strict palette: primary magenta #C026D3, single amber #F59E0B accent (one node or shape highlighted). Transparent square canvas, app-icon proportions. Geometric, minimal, rounded line caps and joins. Style reference: Lucide grid and constellation patterns. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO 3D, NO skeuomorphism. Single coherent composition. Playful but professional, distinct from utilitarian icons.

---

## Brain — Violet `#7C3AED` + Amber accent (TWO candidates to test)

**Product**: B2C life-intelligence meta-product. Brain ingests your sprawl (taxes, finances, docs, decisions) and runs it as durable jobs. Working name only — external brand TBD pending domain availability research. Two glyph directions to test in parallel.

### Brain candidate A — Fill meter

**Metaphor**: vertical gauge with three horizontal bars at increasing fill levels, conveying "knowledge accumulates." Tied to the Brain Fill Meter feature (D51).

**Prompt**:

> A clean modern flat vector app icon for "Brain" — a personal-intelligence app that accumulates context over time. Centered subject: a vertical rounded-rectangle gauge or container with three horizontal fill bars inside at increasing fill levels (short, medium, long), conveying gradual accumulation of knowledge. Strict palette: primary electric violet #7C3AED, single amber #F59E0B accent (one of the fill bars or a small indicator dot at the top). Transparent square canvas, app-icon proportions. Geometric, minimal, rounded line caps and joins. Style reference: Linear's progress indicators, Lucide battery and signal icons. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO 3D, NO skeuomorphism, NO literal brain anatomy. Single coherent shape. Calm, confident, accumulating.

### Brain candidate B — Orbital arcs

**Metaphor**: three concentric arcs around a central node, with a small satellite, conveying "knowledge orbits the user." Tied to the orbital DAG model in BRAIN_PHILOSOPHY.md.

**Prompt**:

> A clean modern flat vector app icon for "Brain" — a personal-intelligence app where knowledge orbits the user. Centered subject: three concentric arcs (different radii, partial — not closed circles) wrapping around a single central node, with one small satellite node at the outer arc, conveying orbital motion. Strict palette: primary electric violet #7C3AED, single amber #F59E0B accent (the central node). Transparent square canvas, app-icon proportions. Geometric, minimal, rounded line caps. Style reference: Linear's geometric system, Lucide's orbit and atom icons, but more minimal. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO 3D, NO skeuomorphism, NO literal atom or planet imagery. Single coherent composition. Calm, intelligent, slightly mystical.

**Run both**, then we pick the one that reads better at favicon size (16×16, 32×32) and lockup size (128×128 against an "Brain" wordmark — though brand external name TBD).

---

## After you generate

1. Pick the cleanest output per product (don't iterate forever — first round + 1 retry is usually enough).
2. Drop the PNG (1024×1024, transparent) into chat.
3. I'll retrace as SVG manually, validate with `xmllint`, render lockup variants (light + dark), drop into `apps/<product>/public/brand/`, regen the brand asset registry, and open a per-product follow-up PR.
4. Bias toward landing one product at a time so we can iterate without giant merges.

## What stays out of these prompts

We are NOT prompting for:

- Wordmarks (we'll author those in SVG with Inter, same as Paperwork Labs and Studio lockups).
- Animated marks, motion variants — same source SVG covers static everywhere.
- Color variants beyond light/dark — the per-product palette IS the variant.
- Logomarks for AxiomFolio (already shipped, see [`apps/axiomfolio/src/assets/logos/`](../../apps/axiomfolio/src/assets/logos/)).
- Logomarks for the publishing imprint — copyright-page attribution only, no consumer mark needed.
