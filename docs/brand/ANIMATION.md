---
title: Brand animation specs — paperclip clip-on, signal pulses, hover wiggles
owner: Paperwork Labs
last_reviewed: 2026-04-26
status: active
---

# Paperwork Labs brand animations

This file specs the **runtime motion** for the parent paperclip mark across three surface tiers: **animated** (frontend nav / hero / splash), **static** (everywhere brand chrome), **straight** (favicon / app icon, no clipping metaphor).

For the prompts that produce the assets, see [`docs/brand/PROMPTS.md`](./PROMPTS.md).

## Tier 1 — Animated: clip-on entrance (P5 clipped wordmark)

**When:** First paint on `paperworklabs.com`, Studio admin sidebar, founder mode hero, app load splash. Plays **once per session** (use `sessionStorage` flag `pwl:clip-animated`); subsequent loads render the static end-state.

**Choreography** (total: ~700 ms):

| Phase | t | Clip transform | Wordmark | Easing |
| --- | --- | --- | --- | --- |
| Pre-roll | 0 ms | `translateY(-72px)` `rotate(-32deg)` `opacity: 0` | `opacity: 0` | — |
| Wordmark fade-in | 0 → 200 ms | (held) | `opacity: 0 → 1` | `easeOut` |
| Clip falls | 200 → 500 ms | `translateY(-72px → 0)` `rotate(-32deg → -10deg)` `opacity: 0 → 1` | (held) | `cubic-bezier(0.16, 1, 0.3, 1)` (easeOutQuart) |
| Clip settles | 500 → 700 ms | `rotate(-10deg → -15deg)` (settle into final tilt, no overshoot toward 0°) | (held) | `cubic-bezier(0.34, 1.56, 0.64, 1)` (easeOutBack, gentle settle) |
| Static end state | 700 ms+ | `translateY(0)` `rotate(-15deg)` `opacity: 1` | `opacity: 1` | — |

**Hover (header only, optional):** subtle wiggle — `rotate(-15deg) → -13deg → -17deg → -15deg` over 320 ms, `easeInOut`. Only triggers when the header is interactive (hover-capable pointer); skip on touch devices.

### Framer Motion implementation (recommended)

Reference component (lives in `packages/ui/src/components/brand/ClippedWordmark.tsx`; once two apps consume it, promote from app-local to package):

```tsx
"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ClipMark } from "./ClipMark";
import { Wordmark } from "./Wordmark";

export function ClippedWordmark({ animated = false }: { animated?: boolean }) {
  const reduce = useReducedMotion();
  const playEntrance = animated && !reduce;

  return (
    <div className="relative inline-flex items-center">
      <motion.span
        className="text-slate-900 dark:text-slate-50"
        initial={playEntrance ? { opacity: 0 } : false}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <Wordmark />
      </motion.span>

      <motion.span
        className="absolute -top-2 -left-1 origin-bottom-right"
        initial={playEntrance ? { y: -72, rotate: -32, opacity: 0 } : { rotate: -15 }}
        animate={{ y: 0, rotate: -15, opacity: 1 }}
        transition={
          playEntrance
            ? {
                opacity: { duration: 0.3, delay: 0.2 },
                y: { duration: 0.3, delay: 0.2, ease: [0.16, 1, 0.3, 1] },
                rotate: {
                  duration: 0.5,
                  delay: 0.2,
                  ease: [0.34, 1.56, 0.64, 1],
                  times: [0, 0.6, 1],
                  values: [-32, -10, -15],
                },
              }
            : { duration: 0 }
        }
        whileHover={playEntrance ? { rotate: [-15, -13, -17, -15], transition: { duration: 0.32 } } : undefined}
      >
        <ClipMark />
      </motion.span>
    </div>
  );
}
```

### CSS-only fallback (for marketing pages without Framer Motion)

```css
@keyframes pwl-clip-on {
  0%   { transform: translateY(-72px) rotate(-32deg); opacity: 0; }
  60%  { transform: translateY(0)     rotate(-10deg); opacity: 1; }
  100% { transform: translateY(0)     rotate(-15deg); opacity: 1; }
}

.pwl-clip {
  transform-origin: bottom right;
  transform: rotate(-15deg);
  animation: pwl-clip-on 700ms cubic-bezier(0.16, 1, 0.3, 1) 200ms both;
}

@media (prefers-reduced-motion: reduce) {
  .pwl-clip {
    animation: none;
    transform: rotate(-15deg);
  }
}
```

### Reduced-motion handling (mandatory)

`useReducedMotion()` (Framer) or `@media (prefers-reduced-motion: reduce)` (CSS): **skip the entrance animation entirely**. Render the static end-state directly. No fade-in either — accessibility users get the brand in its final form on frame 1.

## Tier 2 — Static (clipped wordmark, no animation)

Render the same component with `animated={false}`. Used in:

- Footer attribution on every product page
- OG image / X card / LinkedIn share preview
- Investor deck title slides
- Press kit interior pages
- Email signature
- Business cards, letterhead

## Tier 3 — Straight (no clipping metaphor)

Use **P2 vertical mark** alone or **P3 horizontal lockup** — see `PROMPTS.md` for the surface map. Surfaces:

- Favicon (16 / 32 / 48 px) — vertical mark
- PWA / iOS / Android app icon — vertical mark on rounded-square plate
- Vercel / Render console favicon — vertical mark
- Loading spinner — vertical mark, rotate around center
- Sub-product attribution badge ("by Paperwork Labs") — horizontal lockup

## Where to put each component

| Component | Location | Imports |
| --- | --- | --- |
| `ClipMark` (the SVG glyph alone, diagonal) | `packages/ui/src/components/brand/ClipMark.tsx` | None |
| `VerticalMark` (P2 alone, app icon) | `packages/ui/src/components/brand/VerticalMark.tsx` | None |
| `Wordmark` ("Paperwork Labs" Inter Tight 600) | `packages/ui/src/components/brand/Wordmark.tsx` | None |
| `ClippedWordmark` (P5 — animated/static) | `packages/ui/src/components/brand/ClippedWordmark.tsx` | `ClipMark`, `Wordmark`, `framer-motion` |
| `HorizontalLockup` (P3) | `packages/ui/src/components/brand/HorizontalLockup.tsx` | `ClipMark`, `Wordmark` |
| `StackedLockup` (P4) | `packages/ui/src/components/brand/StackedLockup.tsx` | `VerticalMark`, `Wordmark` |

`packages/ui` already exposes the brand surface; new components live alongside existing brand exports.

## Anti-patterns (do not ship)

- **Re-running the entrance on every nav.** Once per session (`sessionStorage`); persists across SPA route changes.
- **Animating the wordmark.** Wordmark fades in, that's all — never tilt it, never animate it letter-by-letter, never "type it out."
- **Shadow under the clip during animation.** Adds complexity, breaks the flat-vector aesthetic.
- **Bouncing past −15° final tilt.** Settle is monotonic toward final (e.g., −10° → −15°); do not bounce *past* the final position toward 0° (e.g., land at −15°, then bounce to −5°).
- **Animating the amber span.** The amber moment is part of the static composition; do not pulse it, fade it in last, or color-shift it.
- **Using the clipped composition as a favicon.** The clipping metaphor needs ≥24 px to read. Use P2 vertical mark below 24 px.
- **Triggering on scroll.** First paint only, then static. Scroll triggers feel gimmicky for a brand mark.

## Performance budget

- Total CSS / JS for the animated component: ≤ 6 KB gzipped (Framer Motion is already loaded in most apps; component itself is < 1 KB).
- Single composite layer — `transform` and `opacity` only (GPU-accelerated, no layout thrashing).
- Entrance animation completes in 700 ms; no blocking work after that frame.
- Reduced-motion users skip the animation entirely; component renders in 1 paint.

## Open follow-ups

- [ ] Compose final SVG layered version of P5 (clip-front above type, clip-back hidden) — owner: brand
- [ ] Decide if Studio admin sidebar gets the entrance animation or stays static (founder call)
- [ ] Verify reduced-motion path with VoiceOver + axe-core
- [ ] Build Storybook story for `ClippedWordmark` with all three states (animated, static, reduced-motion)
- [ ] Migrate consumers in `apps/paperworklabs/` and `apps/studio/` to the new component once it lands in `packages/ui`
