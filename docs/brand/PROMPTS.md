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

**Status:** No final repo SVG. Interim hand lockups in `apps/studio/public/brand/` — **replace** when the AI mark below is retraced. Parent **does not** use Azure for the mark; that palette is Studio + AxiomFolio (chain-of-life), not the paperclip.

**TIGHT prompt (recommended):**

> Square app mark, 1:1, 1024×1024, transparent. A single flat vector: a Gem-style **continuous wire paperclip** — one unbroken line, rounded corners, constant stroke. **Primary: slate #0F172A** for the entire clip **except** one short segment (outer return bend or one “catch” span) in **amber #F59E0B** as the *only* second color. No gradient, no 3D, no metal texture. Favicon-readable at 16px. Style: Stripe, Linear, Notion, Vercel.  
> **DO NOT** show Clippy, eyes, paper sheets, or extra colors.

Use the same two hexes for **any** LLM brief that touches parent social or investor slides: *always* name slate + amber, never Azure, for the **parent** mark.

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
