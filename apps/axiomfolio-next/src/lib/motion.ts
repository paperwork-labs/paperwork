/**
 * Motion primitives for AxiomFolio.
 *
 * Single source of truth for easings, durations, and reusable framer-motion
 * `Variants`. This file is intentionally pure data + a tiny hook so it stays
 * tree-shakable; component files import `motion` from `framer-motion`
 * themselves.
 *
 * All consumers must additionally call `useReducedMotion()` (or the
 * `useMotionPreset` hook here) so users with reduced-motion preference get
 * an instant no-op variant — the global `prefers-reduced-motion` CSS rules
 * cover CSS animations only, not framer-motion transitions.
 */
import { useReducedMotion, type Variants } from "framer-motion";

type CubicBezier = [number, number, number, number];

/**
 * Named cubic-bezier easing curves.
 *
 * - `standard`   — Material standard, balanced accel/decel for most UI.
 * - `emphasized` — Material 3 emphasized, snappier into final position.
 * - `spring`     — Subtle ~10% overshoot, good for badges and small reveals.
 * - `glide`      — Strong decel curve, pairs with chart reveals so the data
 *                  appears to "settle" rather than slam into place.
 */
export const EASE = {
  standard: [0.4, 0, 0.2, 1] as CubicBezier,
  emphasized: [0.2, 0, 0, 1] as CubicBezier,
  spring: [0.34, 1.56, 0.64, 1] as CubicBezier,
  glide: [0.16, 1, 0.3, 1] as CubicBezier,
} as const;

/** Semantic durations in seconds. */
export const DURATION = {
  instant: 0.1,
  fast: 0.18,
  base: 0.22,
  medium: 0.36,
  slow: 0.6,
  chartReveal: 0.8,
} as const;

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: DURATION.base, ease: EASE.standard },
  },
  exit: {
    opacity: 0,
    transition: { duration: DURATION.fast, ease: EASE.standard },
  },
};

export const slideUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.medium, ease: EASE.emphasized },
  },
  exit: {
    opacity: 0,
    y: -8,
    transition: { duration: DURATION.fast, ease: EASE.standard },
  },
};

export const slideDown: Variants = {
  hidden: { opacity: 0, y: -12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.medium, ease: EASE.emphasized },
  },
  exit: {
    opacity: 0,
    y: 8,
    transition: { duration: DURATION.fast, ease: EASE.standard },
  },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: DURATION.medium, ease: EASE.spring },
  },
  exit: {
    opacity: 0,
    scale: 0.98,
    transition: { duration: DURATION.fast, ease: EASE.standard },
  },
};

/**
 * Left-to-right reveal using `clipPath`. Use on the chart container itself
 * (not inner SVG paths) so the entry feels uniform regardless of chart type.
 */
export const chartReveal: Variants = {
  hidden: { clipPath: "inset(0% 100% 0% 0%)", opacity: 0 },
  visible: {
    clipPath: "inset(0% 0% 0% 0%)",
    opacity: 1,
    transition: { duration: DURATION.chartReveal, ease: EASE.glide },
  },
};

/**
 * Factory: returns a parent variant that staggers child motion components.
 * Defaults to 60 ms — slow enough to read, fast enough to feel responsive.
 */
export function staggerChildren(staggerMs: number = 60): Variants {
  return {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: staggerMs / 1000,
        delayChildren: 0,
      },
    },
    exit: {
      transition: {
        staggerChildren: Math.max(20, staggerMs / 2) / 1000,
        staggerDirection: -1,
      },
    },
  };
}

const PRESETS = {
  fadeIn,
  slideUp,
  slideDown,
  scaleIn,
  chartReveal,
} as const;

export type MotionPresetName = keyof typeof PRESETS;

/**
 * No-op variant returned when `useReducedMotion()` is true. The element is
 * mounted in its final visible state instantly — no transform, no opacity
 * fade, no spring overshoot.
 */
export const INSTANT: Variants = {
  hidden: { opacity: 1 },
  visible: { opacity: 1, transition: { duration: 0 } },
  exit: { opacity: 1, transition: { duration: 0 } },
};

/**
 * Returns the requested preset, or an instant no-op variant when the user
 * has expressed a reduced-motion preference. Always pair with `motion.*`
 * components and pass through `initial="hidden" animate="visible"`.
 */
export function useMotionPreset(name: MotionPresetName): Variants {
  const reduced = useReducedMotion();
  if (reduced) return INSTANT;
  return PRESETS[name];
}
