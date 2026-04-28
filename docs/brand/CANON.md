---
title: Paperwork Labs brand canon
owner: brand
last_reviewed: 2026-04-27
doc_kind: reference
domain: company
status: canonical
---

# Brand canon

Single source of truth for marks, palettes, and visual grammar. Voice, tone, legal copy, and social handles remain in [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc) (always-on rule).

If a logo, palette, or grammar rule is **not** in this file, it is **not canonical**. Anything else in `docs/brand/` is historical; do not cite it.

## Family principle

**Organic similarity > forced unification.** Products share a *droplet + dot* visual vocabulary (count, layout, hue vary); they do **not** share one silhouette or one parent hue. What aligns across the portfolio: Inter wordmarks at the same weight/spacing, shared `viewBox` grammar, surface-aware ink, and the legal "by Paperwork Labs" attribution.

What is **not** the family thread: a single parent colorway cloned onto every app, or "every mark gets an amber accent."

## Asset lock status (read this before touching any brand file)

The agent constraint is simple: **locked = ship as-is, exploring = founder-only, garbage = delete on sight.**

| Status | What it means | Who can edit |
| --- | --- | --- |
| **LOCKED** | Founder-approved canonical mark. Ships in product. | No one without explicit founder direction. |
| **EXPLORING** | Founder is iterating on it. Currently shipped but not final. | **Founder only.** Agents must not touch. |
| **GARBAGE** | Hand-authored placeholder, agent-authored debris, or pre-canon mistake. | Delete on sight; replace references with the locked mark. |

### Locked marks

| File | Subject | Note |
| --- | --- | --- |
| [`apps/axiomfolio/src/assets/logos/axiomfolio-icon-star.svg`](../../apps/axiomfolio/src/assets/logos/axiomfolio-icon-star.svg) | AxiomFolio — 4-petal droplet + center dot | Family anchor. The droplet primitive every other product mark borrows. |
| [`apps/distill/public/brand/distill-icon.svg`](../../apps/distill/public/brand/distill-icon.svg) | Distill — opposing droplets + center dot | Founder-chosen composition. |

### Exploring marks (founder iterates; agents stay out)

| File | Subject |
| --- | --- |
| [`apps/filefree/public/brand/filefree-icon.svg`](../../apps/filefree/public/brand/filefree-icon.svg) | FileFree — 3 droplets converging on a dot |
| [`apps/launchfree/public/brand/launchfree-icon.svg`](../../apps/launchfree/public/brand/launchfree-icon.svg) | LaunchFree — droplet + cyan dot |
| [`apps/trinkets/public/brand/trinkets-icon.svg`](../../apps/trinkets/public/brand/trinkets-icon.svg) | Trinkets — asymmetric droplet pair + dot |

### Locked PNG renders (parent paperclip — P1/P2/P3/P4)

The parent paperclip mark is **PNG-first** (AI-generated, founder-approved) until the founder picks the P5 clipped-wordmark winner and we ship final SVG retraces. Until then, treat these PNGs as canonical and reference them via `next/image` in Next.js apps or plain `<img>` elsewhere (do not embed as inline base64).

| File | Use |
| --- | --- |
| [`apps/studio/public/brand/renders/paperclip-LOCKED-canonical-1024.png`](../../apps/studio/public/brand/renders/paperclip-LOCKED-canonical-1024.png) | **P1 — horizontal lockup** (paperclip + “Paperwork Labs” wordmark). Marketing, OG, Studio header/sign-in, and any React surface that needs the full parent mark. |
| [`apps/studio/public/brand/renders/paperclip-LOCKED-canonical-icon-1024.png`](../../apps/studio/public/brand/renders/paperclip-LOCKED-canonical-icon-1024.png) | **P2 — vertical icon** (favicon-style square glyph). |
| [`apps/studio/public/brand/renders/paperclip-vertical-1024-v1.png`](../../apps/studio/public/brand/renders/paperclip-vertical-1024-v1.png) | P2 vertical — secondary tile |
| [`apps/studio/public/brand/renders/paperclip-lockup-horizontal-v1.png`](../../apps/studio/public/brand/renders/paperclip-lockup-horizontal-v1.png) | P3 horizontal lockup (header bar) |
| [`apps/studio/public/brand/renders/paperclip-lockup-stacked-v1.png`](../../apps/studio/public/brand/renders/paperclip-lockup-stacked-v1.png) | P4 stacked lockup (square card) |

React surfaces import these paths from the consuming app’s `public/` root (e.g. `src="/brand/renders/paperclip-LOCKED-canonical-1024.png"` with Next.js `<Image>`). Copy the files into each app’s `public/brand/renders/` when the app cannot rely on another package’s static assets.

### Needs founder review (do not delete, do not canonize)

These pre-canon SVGs exist on disk and are referenced from app layouts. They are **not** in the locked or exploring list, but the founder has not explicitly classified them as garbage either. Until the founder reviews, agents must treat them as read-only and must not import them into new components.

| File | Currently used in |
| --- | --- |
| `apps/axiomfolio/src/assets/logos/axiomfolio-lockup.svg` | [`apps/axiomfolio/src/app/layout.tsx`](../../apps/axiomfolio/src/app/layout.tsx) |
| `apps/axiomfolio/src/assets/logos/axiomfolio-lockup-surface.svg` | (light-surface variant; check refs) |
| `apps/axiomfolio/src/assets/logos/axiomfolio-lockup-dark.svg` | (dark-surface variant; check refs) |
| `apps/studio/public/brand/studio-icon.svg` | Studio favicon set |
| `apps/studio/public/brand/studio-lockup.svg` | Studio header lockup |
| `apps/studio/public/brand/studio-lockup-dark.svg` | Studio header lockup (dark) |

### Garbage (delete; replace references)

| File | Replace references with |
| --- | --- |
| `apps/axiomfolio/src/assets/logos/axiomfolio.svg` | `axiomfolio-icon-star.svg` |
| `apps/studio/public/brand/paperwork-labs/paperclip/mark-vertical.svg` | `renders/paperclip-LOCKED-canonical-icon-1024.png` |
| `apps/studio/public/brand/paperwork-labs/paperclip/mark-diagonal.svg` | `renders/paperclip-LOCKED-canonical-1024.png` |
| `apps/studio/public/brand/paperwork-labs/paperclip/clipped-wordmark.svg` | (no replacement until founder picks P5 winner) |
| `apps/studio/public/brand/paperwork-labs/icon.svg` | `renders/paperclip-LOCKED-canonical-icon-1024.png` |
| `apps/studio/public/brand/paperwork-labs/lockup.svg` | `renders/paperclip-lockup-horizontal-v1.png` |
| `apps/studio/public/brand/paperwork-labs/lockup-dark.svg` | `renders/paperclip-lockup-horizontal-v1.png` (same; surface tint via CSS) |

## Per-product full palette

Each row is the lock for marks, social templates, and (after the theme migration sprint) product UI. **Primary** and **accent** are fixed for the glyph; **ink** shifts with light vs dark surface.

| Product | Primary | Accent | Ink (light) | Ink (dark) | Primary on dark |
| --- | --- | --- | --- | --- | --- |
| Paperwork Labs (parent) | Slate `#0F172A` | Amber `#F59E0B` | `#0F172A` | `#F8FAFC` | slate stays; amber → `#FBBF24` |
| Studio | Azure `#3274F0` | Amber `#F59E0B` | `#0F172A` | `#F8FAFC` | `#60A5FA` |
| AxiomFolio | Azure `#3274F0` | Amber `#F59E0B` | `#0F172A` | `#F8FAFC` | `#60A5FA` |
| FileFree | Indigo `#4F46E5` | Lime `#84CC16` | `#0F172A` | `#F8FAFC` | `#818CF8` |
| LaunchFree | Sky `#0284C7` | Cyan `#06B6D4` | `#0C4A6E` | `#F8FAFC` | `#38BDF8` |
| Distill | Teal `#0F766E` | Burnt orange `#C2410C` | `#115E59` | `#F8FAFC` | `#14B8A6` |
| Trinkets | Indigo `#6366F1` | Sky cyan `#38BDF8` | `#1E1B4B` | `#F8FAFC` | `#A5B4FC` |
| Brain | Emerald `#10B981` | Mint `#6EE7B7` | `#0F172A` | `#F8FAFC` | `#34D399` |

`#F8FAFC` is the canonical light-surface token. `#0F172A` is the canonical dark anchor. Both are shared; everything else varies by product.

## Visual grammar

Mandatory for any new mark.

1. **viewBox** — `0 0 128 128` for icons, `0 0 720 150` for lockups.
2. **Padding** — ~16px breathing room from viewBox edges to mark.
3. **Stroke** — `9–11` for stroke-based glyphs; round caps + joins; filled droplets may use fill (AxiomFolio + FileFree family).
4. **One accent per glyph.** Always one. Never two. The accent is the *earned moment*, not decoration.
   - **Parent paperclip exception**: the single amber moment may traverse a curve and the adjacent straight as one continuous span (~⅙–¼ of perimeter), never two discrete spans. Parent-only.
5. **No gradients, drop shadows, or filters** in the SVG file. Marketing surfaces add ambient effects in CSS.
6. **Wordmark** — Inter 600, `letter-spacing: -0.5`, `font-size: 62`. System stack fallback.
7. **Wordmark color is surface-aware** — see Ink columns above. On dark surfaces wordmark always = `#F8FAFC` (verified against AxiomFolio's deployed login).

## When to use SVG vs PNG

| Surface | Format | Why |
| --- | --- | --- |
| Favicon (16/32/48) | PNG | Browsers rasterize anyway; PNG keeps anti-aliased AI artwork crisp at 16px. |
| OG image / social card | PNG | Static, big canvas, photoreal-friendly. |
| Parent paperclip (any in-app or marketing surface) | PNG via `next/image` or `<img>` | Only the locked renders under `apps/studio/public/brand/renders/` (and copies in each app’s `public/`). Do not recreate geometry in TSX/SVG. |
| Typesetting wordmark (`packages/ui/src/components/brand/Wordmark.tsx`) | SVG (`<text>` in Inter Tight) | Typesetting-only; not the paperclip. Parent lockups use the **P1** PNG above. |
| Locked droplet product marks | SVG inline where appropriate | Distinct from the parent paperclip; follow per-product rows in this doc. |
| Marketing hero | PNG | Allows CSS sheen / filter / blur to ride on top. |
| Print / spec sheet | SVG (locked droplet marks only) | Vector for press. Parent paperclip ships as raster until retrace. |

Shared typesetting for “Paperwork Labs” lives in [`packages/ui/src/components/brand/Wordmark.tsx`](../../packages/ui/src/components/brand/Wordmark.tsx). Parent paperclip compositions are **not** implemented as React geometry components — consumers reference the locked PNG paths from their app `public/` folders.

## Workflows

### Adding a new lockup after an icon exists

1. Pull the **Ink** and **Primary** columns from the palette table.
2. `720×150` viewBox, Inter 600, no extra accent beyond the product rule.
3. `xmllint --noout` on every SVG; place beside the icon in `public/brand/`.
4. Generate raster set (`16/32/64/128/256/512/1024`) into `public/brand/renders/`.
5. Update favicons and metadata in the consuming app's `app/layout.tsx`.

### Replacing a garbage SVG

1. Delete the SVG.
2. `rg -l "<filename>"` to find every reference.
3. Replace each reference with the canonical mark per the Garbage table above.
4. If the reference was an `<img src="...">` for a PNG-replacement, prefer `<Image>` from `next/image` with explicit `width`/`height`.

### Generating a new AI mark

When the founder asks for a new variant:

1. Use the locked palette hexes verbatim. Reject any model output that introduces an unlisted hue.
2. 1024×1024, transparent background, retrace-friendly geometry.
3. Land the chosen render in `apps/<app>/public/brand/renders/<name>-v<N>.png`.
4. Mark it **EXPLORING** in this file's lock-status table until founder confirms.
5. Once locked, move it to `apps/<app>/public/brand/<name>.png` (or retrace to SVG) and promote it to the **LOCKED** table here.

## Animation

Parent **P5 clipped wordmark** runtime motion (see § **Locked PNG renders** / **When to use SVG vs PNG** above): entrance **once per session** (e.g. a `sessionStorage` flag—never on every SPA navigation); total choreography ~**700 ms** (wordmark opacity, clip translate / rotate settling near **−15°**); optional subtle **hover wiggle** only for hover-capable pointers. **`prefers-reduced-motion: reduce`**: skip the entrance entirely; render the static end-state. Use **`transform` + `opacity` only** for the animated path; no shadows on the clip during motion.

**Do not:** re-run entrance on route changes; animate the wordmark beyond a simple fade-in; animate or pulse the amber span; bounce past the final clip tilt; use the full P5 clipped composition below **~24 px** (use vertical / lockup tiers instead—see **When to use SVG vs PNG**).

**Future queue:** final layered SVG for P5 (z-order); Storybook / a11y verification for motion paths; `SessionClippedWordmark` (Studio) currently renders the **P1** PNG statically — session-once entrance will return as a PNG sprite sequence under `t2-animation` once the founder picks the sprite source (per this §).

## Don'ts

- Do not put the parent paperclip on a consumer product page — it is parent-brand only.
- Do not recolor a locked mark — open a brand review.
- Do not add a second accent in the same glyph.
- Do not hand-author an SVG that imitates the droplet family — agents authoring marks has been the source of every "garbage" entry above.
- Do not author hand-drawn paperclip geometry in TSX/JSX (`<path d="M ... A ... 0 0 1 ...">` paths that imitate the droplet family). Same anti-pattern as hand-authored SVGs. Always reference the locked PNG renders under `apps/studio/public/brand/renders/` via `<Image>` from `next/image` (Next.js apps) or plain `<img>` (non-Next surfaces).
- Do not cite the legacy `PROMPTS.md`, `ANIMATION.md`, or `research/` files under `docs/brand/`. Those were deleted in #314; if you find them in a stale checkout, ignore.

## Related

- [`.cursor/rules/brand.mdc`](../../.cursor/rules/brand.mdc) — voice, tone, legal copy, social handles. Always-on rule.
- [`packages/ui/src/components/brand/`](../../packages/ui/src/components/brand/) — Shared typesetting (`Wordmark`); parent paperclip = locked PNGs in consuming apps.
