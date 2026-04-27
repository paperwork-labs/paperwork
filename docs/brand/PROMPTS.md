---
title: Brand prompts — AI image-generation prompts per consumer product
owner: Paperwork Labs
last_reviewed: 2026-04-26
status: active
---

# Brand prompts

**Locked full palettes** for every consumer-facing, LLM, or image model task (marketing copy, social, OG images, ad creative, in-app “hero” stills). Use the tables below as hard constraints: if the model invents a new primary or accent, reject the output.

**Icon status (2026-04-26):** Droplet-family SVG marks are **shipped in-repo** for FileFree, LaunchFree, Distill, and Trinkets (see paths in each section). **Paperwork Labs parent** and **Brain** are still **AI → SVG** — use the prompts below, then retrace, `xmllint --noout`, and land in `apps/studio/public/brand/` (parent) or the Brain app when it exists.

## Why this exists

Hand-authored geometric marks work for utility surfaces (Studios' grid) but homogenize when copy-pasted across six consumer marks. The droplet + dot system keeps **organic similarity** (shared vocabulary) without **forced unification** (same silhouette). The five parallel 2026-04-25 dives plus founder locks 2026-04-26 set the hues; this file bakes them into any generative brief.

## Locked palettes per product (use verbatim in prompts)

| Product | Primary | Accent | Wordmark (light surface) | Wordmark (dark surface) | Neutral light | Neutral dark | Default app surface |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Paperwork Labs (parent) | Slate ink `#0F172A` | Amber `#F59E0B` (one segment) | `#0F172A` | `#F8FAFC` | `#F8FAFC` | `#0F172A` | both |
| AxiomFolio | Azure `#3274F0` | Amber `#F59E0B` | `#0F172A` | `#F8FAFC` | `#F8FAFC` | `#0F172A` | dark |
| FileFree | Indigo `#4F46E5` | Lime `#84CC16` | `#0F172A` | `#F8FAFC` | `#F8FAFC` | `#020817` / `#0F172A` | dark |
| LaunchFree | Sky `#0284C7` | Cyan `#06B6D4` | `#0C4A6E` | `#F8FAFC` | `#F8FAFC` | `#0A0F1A` / `#0F172A` | dark |
| Distill | Teal `#0F766E` | Burnt orange `#C2410C` | `#115E59` | `#F8FAFC` | off-white / `#F8FAFC` | `#0F172A` | light |
| Trinkets | Indigo `#6366F1` | Sky cyan `#38BDF8` | `#1E1B4B` | `#F8FAFC` | `#F8FAFC` | `#0C0A09` / `#0F172A` | light |
| Brain | Emerald `#10B981` | Mint `#6EE7B7` | `#0F172A` | `#F8FAFC` | `#F8FAFC` | `#0F172A` | dark |

**On-dark stroke variants** (for raster mockups, not new brand colors): parent clip stays ink with amber highlight; Axiom/Studio Azure → `#60A5FA`; FileFree indigo → `#818CF8`; LaunchFree sky → `#38BDF8`; Distill teal → `#14B8A6`; Trinkets indigo → `#A5B4FC`; Brain emerald → `#34D399`.

## Universal prompt scaffold

Substitute product-specific names and the locked hexes from the table.

> **A clean modern flat vector app icon for "{PRODUCT}". Centered subject: {METAPHOR}. Strict palette: primary {PRIMARY_HEX} ({PRIMARY_NAME}), single {ACCENT_HEX} ({ACCENT_NAME}) accent (dot, segment, or short stroke only). Transparent square canvas, subject ~60% of frame. Rounded line caps and joins. Style: Linear, Vercel, Notion, Lucide. NO text, NO wordmark, NO gradients, NO photorealism, NO drop shadows, NO 3D, NO stock-photo lighting.**

Also state: **1024×1024**, transparent background, retrace-friendly geometry.

---

## Paperwork Labs (parent) — Slate `#0F172A` + single Amber `#F59E0B` segment

**Status (2026-04-26 LOCK):** Five-prompt system locked by founder review. **P1** diagonal (expressive default) + **P2** vertical (canonical icon) + **P3** horizontal lockup + **P4** stacked lockup + **P5** clipped wordmark (the clip *clipping* "Paperwork Labs"). v1 reference renders shipped to `apps/studio/public/brand/renders/`. Runtime motion specs (clip-on entrance, hover wiggle, reduced-motion handling) live in [`docs/brand/ANIMATION.md`](./ANIMATION.md). Final canonical SVG composition still pending retrace; AI prompts below are the source of truth for raster generation + Nano Banana Pro image-edit refinement.

Parent **does not** use Azure for the mark; that palette is Studio + AxiomFolio (chain-of-life). Slate + amber is the **only** parent palette across every surface, every prompt, every model.

### Amber rule (founder lock, 2026-04-26)

The parent paperclip uses **one continuous amber moment** — but the moment may **traverse a curve and an adjacent straight as a single span** (e.g., the inner U-bend curling into the inner straight wire below it). Visually this can read as "amber in two zones," but geometrically it's one continuous segment, ~⅙ to ¼ of the wire's perimeter, never broken into two discrete spans separated by slate. The continuous-but-extended treatment is what makes the parent mark distinctive (vs. the per-product family's tighter, single-zone accents).

This is **parent-only**. Other product marks (FileFree, LaunchFree, Distill, Trinkets, Brain) keep the tighter "exactly one zone" rule per `.cursor/rules/brand.mdc` §Visual grammar.

### Why two orientations

The diagonal clip is **expressive** — dynamic, instantly recognizable as a paperclip, lands well on social / OG cards / hero stills / the P5 clipped wordmark composition. The vertical clip is **the canonical icon** — symmetric long axis, aligns to wordmark cap-height for stacked lockups, and gets more vertical pixels at 16/32 px favicon sizes (cleaner silhouette where it matters most). Both are first-class; pick by surface, not by taste. (Pattern reference: Stripe, Linear, Notion all run mark in multiple orientations against the same brand spine.)

### P1 — Diagonal mark (expressive default)

**Use for:** OG cards, social heroes, investor-deck title slides, marketing illustrations, P5 clipped-wordmark composition. **Default for everything except favicon / app icon / spinner / stacked lockup.**

**Full prompt (paste as one block):**

> Square app mark, 1:1, 1024×1024, transparent. A single flat vector: a Gem-style **continuous wire paperclip** rotated about **+30° to +45° from horizontal** — one unbroken line, rounded corners, constant stroke (~9–11 px equivalent at 128 px viewBox). **Primary: slate #0F172A** for the entire clip **except** one continuous amber #F59E0B span that traverses the inner U-bend curve and continues down the adjacent inner straight wire (one geometric moment, ~⅙–¼ of the perimeter, may visually read as "two zones" because the wire bends through it — that's the intent). No gradient, no 3D, no metal texture, no perspective. Subject ~60% of frame, centered, generous breathing room. Favicon-readable at 16 px. Style: Stripe, Linear, Notion, Vercel.
> **DO NOT** break the amber into two discrete spans separated by slate; **DO NOT** show Clippy, eyes, mascot face, paper sheets, gradients, drop shadows, metallic shading, or any third color.

**Reference (founder-generated, locked):** `apps/studio/public/brand/renders/paperclip-LOCKED-canonical-1024.png` (extracted from the horizontal lockup; canonical glyph for the parent paperclip in diagonal orientation).

**Render target (when retraced to SVG):** `apps/studio/public/brand/paperwork-labs-icon.svg` + `apps/studio/public/brand/renders/paperclip-diagonal-{16,32,64,128,256,512,1024}.png`.

### P2 — Vertical mark (canonical icon: favicon, app icon, spinner)

**Use for:** Favicon (16/32/48), PWA / iOS / Android app icon, stacked lockups, loading spinners, sidebar / nav badges, anywhere the surface is more vertical than wide *or* the long axis must align with the pixel grid.

**Full prompt (paste as one block):**

> Square app mark, 1:1, 1024×1024, transparent. A single flat vector: a Gem-style **continuous wire paperclip oriented strictly vertically** — long axis runs top-to-bottom, the inner U-bend (the smaller loop) opens **upward**, the outer return curls **downward**, axis tilt 0° (no rotation). One unbroken line, rounded corners, constant stroke. **Primary: slate #0F172A** for the entire clip **except** one continuous amber #F59E0B span (preferably the right-hand outer return-and-base, traversing the straight + curve as one moment — same continuous-extended rule as P1). No gradient, no 3D, no metal texture. Centered, ~62% of frame, generous breathing room top + bottom. The vertical bias should be deliberate — the silhouette at 16 px should still read as "paperclip," not "I-beam." Style: Stripe, Linear, Notion, Vercel.
> **DO NOT** rotate even ~5° (it becomes the diagonal mark); **DO NOT** break amber into two discrete spans; **DO NOT** show Clippy, eyes, paper sheets, gradients, drop shadows, or any third color; **DO NOT** widen the loops to a stadium-pill shape (it stops reading as a clip).

**Reference (founder-generated, locked):** `apps/studio/public/brand/renders/paperclip-LOCKED-canonical-icon-1024.png`.

**Render target:** `apps/studio/public/brand/paperwork-labs-icon-vertical.svg` + `apps/studio/public/brand/renders/paperclip-vertical-{16,32,64,128,256,512,1024}.png`.

### P3 — Horizontal lockup (mark + wordmark side-by-side, preview-only)

**Use for:** previewing the lockup composition before composing the final SVG by hand. The shipped lockup is **always** an SVG composed in design tooling (clip from P1 + Inter Tight 600 wordmark) — never a raster from this prompt.

**Full prompt (paste as one block):**

> Centered horizontal logo composition on a transparent canvas, 4:1 aspect ratio, 2048×512 px. **Left half:** the Paperwork Labs paperclip mark — diagonal orientation per P1, slate #0F172A wire with exactly one continuous amber #F59E0B span that traverses the inner U-bend curve into the adjacent inner straight (one geometric moment, two visual zones; ~⅙–¼ of perimeter). The mark's vertical extent equals the cap-height of the wordmark to its right. **Gap:** ~1× cap-height of clean space between mark and wordmark. **Right:** the wordmark "Paperwork Labs" set in **Inter Tight 600** (semibold), letter-spacing −0.02 em, color slate #0F172A, baseline-aligned to the mark's baseline, two words separated by a single space, no tagline, no underline. Subject is optically centered on the canvas (not pixel-centered — account for the asymmetric weight of mark + wordmark). Style: Stripe, Linear, Notion, Vercel — quiet, balanced, breathable.
> **DO NOT** break amber into two discrete spans; **DO NOT** show drop shadows, gradients, italic type, multiple weights mixed, ALL CAPS, decorative serifs, or any third color; **DO NOT** add a tagline, registration mark, or decorative rule between mark and wordmark.

> ⚠️ **Preview-only.** Final ships as composed SVG: clip from P1 + Inter Tight 600 wordmark from design tooling.

**Reference (founder-generated, locked):** `apps/studio/public/brand/renders/paperclip-lockup-horizontal-v1.png`.

### P4 — Stacked lockup (vertical mark above wordmark, preview-only)

**Use for:** previewing the stacked composition (press kit covers, square social profile graphics, vertical badges) before SVG composition.

**Full prompt (paste as one block):**

> Centered vertical logo composition on a transparent canvas, 1:1.4 aspect ratio, 1024×1434 px. **Top:** the Paperwork Labs paperclip mark — vertical orientation per P2 (long axis 0°, inner loop up, outer return down), slate #0F172A wire with one continuous amber #F59E0B span (continuous-extended rule). Mark height ~38% of canvas. **Gap:** ~⅓ × the mark's height of clean space between mark and wordmark. **Bottom:** the wordmark "Paperwork Labs" set in **Inter Tight 600**, letter-spacing −0.02 em, color slate #0F172A, two words on one line, optical-center-aligned with the mark above. No tagline, no decorative rule, no underline, no registration mark. Style: Stripe, Linear, Notion, Vercel.
> **DO NOT** show drop shadows, gradients, italics, ALL CAPS, decorative serifs, or any third color; **DO NOT** stack the wordmark on two lines.

> ⚠️ **Preview-only.** Final ships as composed SVG, same as P3.

**Reference (founder-generated, locked):** `apps/studio/public/brand/renders/paperclip-lockup-stacked-v1.png`.

### P5 — Clipped wordmark (the clip *clipping* "Paperwork Labs", the metaphor finally lands)

**Founder rationale (2026-04-26):** *"When I was actually thinking paperclip, I was thinking it would clip the Paperwork Labs text top-left."* P3/P4 lockups treat the clip as a logo *beside* / *above* the wordmark — fine, conventional, but the paperclip metaphor is wasted there. P5 puts the clip *on* the wordmark, top-left, the way a real paperclip pins a sheet of paper. **This is the most distinctive surface treatment** of the four; we use it where the brand can shine.

**Use for:** paperworklabs.com header (animated entrance), Studio admin sidebar, founder hero, splash on first app load, business cards, press kit interior, OG cards. **Do NOT** use for favicon (clip detail dies at 16 px) or app icon (use P2 vertical instead).

**Full prompt (paste as one block):**

> Horizontal logo composition on a transparent canvas, 5:1 aspect ratio, 2560×512 px. **Wordmark:** "Paperwork Labs" set in **Inter Tight 600** (semibold), letter-spacing −0.02 em, color slate #0F172A, two words separated by a single space, baseline near canvas vertical center, ~78% canvas width. **Paperclip:** a Gem-style continuous wire paperclip per P1 (slate #0F172A wire with one continuous amber #F59E0B span across the inner curve + adjacent straight), **rotated −12° to −18° (top tilted left)**, positioned over the **top-left corner of the capital "P"** so that the clip's inner U-bend hooks over the cap-line of the type and the outer return implies wrapping behind the wordmark (occlusion: render only the front-facing portion of the clip; the back portion behind the type is hidden, never drawn over the type). The clip is sized so its long axis is ~1.4× the cap-height of the type; the clip "grips" only the first 1–1.5 letterforms (the "P" and partly the "a"). Constant stroke, rounded caps. Subject is optically centered. Style: Stripe, Linear, Notion, Vercel — quiet, intentional, sharp.
> **DO NOT** show drop shadows, gradients, ALL CAPS, italic type, or any third color; **DO NOT** draw the back of the clip on top of the wordmark (it must look like the clip wraps *behind* the type); **DO NOT** position the clip floating beside the wordmark (that's P3, not P5); **DO NOT** add Clippy eyes, paper sheets, or motion lines.

> ⚠️ **Preview-only.** Final ships as composed SVG with z-ordered layers (wordmark mid layer, clip-front top layer, clip-back invisible/clipped). Don't ship a baked raster as the production asset.

**Three states this composition runs in:**

| State | Surface | Behavior |
| --- | --- | --- |
| **Animated** | paperworklabs.com nav, app load splash, Studio sidebar entrance, founder mode hero | Clip animates in, then settles static. See [`docs/brand/ANIMATION.md`](./ANIMATION.md) for choreography + Framer Motion + reduced-motion specs. |
| **Static (clipped)** | Footer attribution, business cards, OG cards, press kit interior, investor decks, email signature | Same composition, no entrance animation. |
| **Straight (unclipped)** | Favicon, PWA / iOS app icon, anywhere clip detail < 24 px | Use **P2 vertical mark alone** or **P3 horizontal lockup**. The clipping metaphor needs ≥24 px to read. |

### Nano Banana Pro edit workflow (image-to-image refinement)

You can refine any of the v1 references above by uploading the PNG to **Nano Banana Pro** (Gemini 2.5 / Imagen 4) and pasting an edit-prompt. Pattern:

1. **Upload** one reference (e.g., `paperclip-lockup-horizontal-v1.png`) as the base image.
2. **Paste the edit prompt below**, substituting the target composition you want.
3. **Generate 3–4 variations**; reject any that introduce a third color, tilt the wordmark, or change the type weight.
4. Save winners back to `apps/studio/public/brand/renders/` with the next version suffix (`-v2`, `-v3`).

**Edit-prompt template (paste as one block, customize the *italics*):**

> Edit this image: keep the slate #0F172A + amber #F59E0B palette, keep the Inter Tight 600 wordmark "Paperwork Labs" exactly as-is. *Reposition the paperclip so it visually clips the top-left corner of the capital "P" — clip rotated −15°, inner U-bend hooks over the cap-line of the type, outer return wraps behind the wordmark (occluded by the type, not drawn over it).* Clip height ~1.4× cap-height. One continuous amber span across the inner curve + adjacent straight on the visible front-facing portion of the clip only. Transparent background. Style: Stripe, Linear, Notion, Vercel. **DO NOT** add gradients, drop shadows, italics, third colors, Clippy faces, motion lines, or paper sheets. **DO NOT** draw any part of the clip *over* the wordmark; clip must appear to grip from the top, not float in front.

**Variation prompts to run in parallel:**

- *"…rotated −10°, gripping only the top-left of the 'P'…"* (subtler grip)
- *"…rotated −22°, gripping the full 'P' and partly the 'a'…"* (more aggressive grip)
- *"…vertical orientation, gripping the top-center of the wordmark from directly above…"* (centered name-tag pose, alt to top-left grip)

**Reject criteria** (auto-fail any output that violates):

- Third color anywhere
- Wordmark tilted, italic, multiple weights, or recolored
- Clip drawn *over* the wordmark (breaks the occlusion / pinning illusion)
- Drop shadow, gradient, or any non-flat shading
- Mark height < 1× cap-height (looks like a typo accent) or > 2× cap-height (looks like a logo collision)
- Amber broken into two discrete spans separated by slate (must be one continuous span across curve + straight)

### When to use which (canonical surface map)

| Surface | Prompt | Why |
| --- | --- | --- |
| **paperworklabs.com header (animated)** | **P5 clipped wordmark** + entrance animation | The metaphor, in motion. Plays once per session. See `ANIMATION.md`. |
| **Studio admin sidebar entrance** | **P5 clipped wordmark** + entrance animation | Same — once per session. |
| **App load splash** | **P5 clipped wordmark** + entrance animation | Same. |
| Footer / "by Paperwork Labs" attribution | **P5 clipped wordmark** (static) OR **P3 horizontal** at small size | P5 if surface is ≥ 200 px wide; P3 below that. |
| OG image / X card / LinkedIn share preview | **P5 clipped wordmark** (static) | Static raster of the clipped composition |
| Investor deck title slide | **P5 clipped wordmark** OR **P4 stacked** | Founder choice per slide rhythm |
| Press kit interior page | **P5 clipped wordmark** (static) | Same |
| Press kit cover / square social profile | **P4 stacked** (composed SVG) | Square / portrait surfaces benefit from vertical stack |
| Marketing illustration / blog hero | **P1 diagonal** | Standalone clip energy, no wordmark |
| OG image when wordmark inappropriate | **P1 diagonal** | Same |
| Favicon 16 / 32 / 48 px | **P2 vertical** | Clip detail dies < 24 px; vertical silhouette holds |
| PWA / iOS / Android app icon | **P2 vertical** on rounded-square plate | Matches OS app-icon norms |
| Browser tab high-DPI (≥64 px) | **P2 vertical** | Consistency with favicon canon |
| Loading spinner / scrubber | **P2 vertical** | Symmetric axis = clean rotation pivot |
| Vercel / Render console favicon | **P2 vertical** | Same favicon canon |

### Dark-surface variant (applies to all five prompts)

For dark backgrounds (`#0F172A` or darker), swap inside the prompt:

| Token | Light surface | Dark surface |
| --- | --- | --- |
| Wire / wordmark | slate `#0F172A` | near-white `#F8FAFC` |
| Accent span | amber `#F59E0B` | amber `#FBBF24` |

Everything else (geometry, gap, type weight, anti-list) is identical. Render dark variants alongside light variants under the same render filename with `-dark` suffix (`paperclip-vertical-256-dark.png`).

### Composition rules (for SVG retrace + lockup hand-composition)

1. `viewBox` for icons: `0 0 128 128` (matches family rule in `.cursor/rules/brand.mdc` §Visual grammar).
2. `viewBox` for lockups: `0 0 720 150` (horizontal) and `0 0 360 504` (stacked).
3. `viewBox` for P5 clipped wordmark: `0 0 1280 256` (5:1).
4. Stroke width: 9–11 at 128-px viewBox. Round caps, round joins.
5. **One continuous amber moment** per parent mark (curve + adjacent straight allowed; never two discrete spans). Length ~⅙–¼ of total perimeter.
6. Wordmark font: Inter Tight 600, `letter-spacing: -0.02em` (≈ -2% / -0.5 px at 24 px). System Inter fallback OK.
7. Wordmark color: slate `#0F172A` on light, near-white `#F8FAFC` on dark. **Never** amber the wordmark.
8. Mark sits to the **left** of wordmark in horizontal lockup (Western reading order); stacked = mark **on top**; P5 = clip *over the top-left corner of "P"*.
9. P5 z-order: wordmark (mid) → clip-front portion (top, visible) → clip-back portion (hidden, not drawn).
10. Clear-space rule: half the mark's height of breathing room on every side; never crowd.

Use slate + amber for **every** parent LLM brief, social caption brief, OG-image generation, or investor-slide brief. Never Azure (that's Studio + AxiomFolio). Never green / teal / indigo / sky / purple. Two hexes, full stop.

---

## AxiomFolio

**Canonical mark (no AI needed for icon):** `apps/axiomfolio/src/assets/logos/axiomfolio-icon-star.svg`  
Use **Azure `#3274F0` + Amber `#F59E0B`** in any generative still (hero, LinkedIn, conference slide) for consistency with the shipped vector.

---

## FileFree — Indigo `#4F46E5` + Lime `#84CC16` accent

**Canonical icon (locked):** `apps/filefree/public/brand/filefree-icon.svg`  
**Renders:** `apps/filefree/public/brand/renders/filefree-icon-{16,32,64,128,256,512,1024}.png`

**Why this palette (one line):** TurboTax / H&R / Intuit own green+blue; indigo + lime is money-positive and modern without copying those lanes.

**For NEW marketing** (banners, not replacing the app icon), you may still use the **universal scaffold** with: three droplet shapes converging on a **lime** center dot, **indigo** droplets, flat vector, same hexes. Do **not** override the in-product icon with a different shape without brand review.

**Legacy image prompt** (if generating a non-icon illustration):

> … Strict palette: indigo #4F46E5, single lime #84CC16 accent … (see universal scaffold; folded-document metaphors are optional; icon geometry in-repo is the droplet lock.)

---

## LaunchFree — Sky `#0284C7` + Cyan `#06B6D4` accent

**Canonical icon (locked):** `apps/launchfree/public/brand/launchfree-icon.svg`  
**Renders:** `apps/launchfree/public/brand/renders/launchfree-icon-{16…1024}.png`

**Why (one line):** Sky + cyan reads launch + momentum vs LegalZoom / ZenBusiness / Atlas palette clustering.

**Illustration prompt** (optional): *Single droplet + cyan dot below* — do not contradict the lock; use the same hexes for any new LaunchFree OG card.

---

## Distill — Teal `#0F766E` + Burnt orange `#C2410C` accent

**Canonical icon (locked):** `apps/distill/public/brand/distill-icon.svg`  
**Renders:** `apps/distill/public/brand/renders/distill-icon-{16…1024}.png`

**Why (one line):** LibreTexts-style distillation (vapor / condensate / essence) → teal + orange; avoids Drake/ProSeries blues; only B2B mark so must not collide with AxiomFolio azure in mixed decks.

**Illustration prompt** (optional): *Opposed droplets + center dot*; keep teal on droplets, burnt orange on the center; no gradients in source art.

---

## Trinkets — Indigo `#6366F1` + Sky cyan `#38BDF8` accent

**Canonical icon (locked):** `apps/trinkets/public/brand/trinkets-icon.svg`  
**Renders:** `apps/trinkets/public/brand/renders/trinkets-icon-{16…1024}.png`

**Why (one line):** Sibling to FileFree; funnel is `tools.filefree.ai` → `filefree.ai` — one hue family, lighter surfaces, friendlier illustration.

**Illustration prompt** (optional): *Asymmetric droplet pair + one sky-cyan highlight dot*; never swap to FileFree’s exact 3+1 lock without review.

---

## Brain — Emerald `#10B981` + Mint `#6EE7B7` accent

**Status:** **No** repo SVG. **Droplet family does not apply** — Brain is a **brain** glyph (founder: keep the metaphor obvious).

**Why (one line):** brain.ai / Mem / Reflect / Notion AI own violet; emerald + mint signals growth + custody (D49 Memory Moat) without purple cliché.

**TIGHT prompt (recommended):**

> Square app mark, 1:1, 1024×1024, transparent. A **stylized brain** as one continuous **geometric line** — clean rounded gyri, uniform stroke, NO photorealism, NO grey-matter texture. **Primary: emerald #10B981** for the outline; **exactly one** accent moment in **mint #6EE7B7** (one fold or one inner dot). No gradient, no 3D, no medical flesh tones, no “character” face. Favicon-silhouette at 16px must read as “brain.” Style: Stripe / Linear / Notion — B2B calm, not clinical, not cute mascot.  
> **DO NOT** add eyes, mouth, or violet/purple.

**Optional (legacy explorations only — not required if founder locks single brain mark):** fill-meter or orbital candidates may be explored only if the brain-first prompt fails; same **#10B981 / #6EE7B7** palette and same anti-violet rule.

---

## After you generate (human + agent)

1. **Parent + Brain only:** pick one PNG, retrace to SVG, `xmllint --noout`, then PR into `apps/studio/public/brand/` (parent) or the Brain app `public/brand/`.
2. For **all raster marketing**: pull hexes only from the **Locked palettes** table; drop renders into the product’s `public/brand/renders/` if they must ship in-repo.
3. One product per change when touching favicon wiring; icon files are already present for the four droplet apps.

## What stays out of these prompts

- Wordmark SVGs: Inter 600 in design tooling — not generated in Midjourney.
- AxiomFolio: do not regenerate a competing primary mark; use shipped assets.
- Publishing imprint: no consumer mark; copyright line only.
- No extra palette columns beyond the locked primaries, accents, and surface-aware inks above (unless a brand review opens a new row).
