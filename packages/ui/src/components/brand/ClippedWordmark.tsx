"use client";

import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";

import { ClipMark } from "./ClipMark";
import { Wordmark } from "./Wordmark";

export interface ClippedWordmarkProps {
  /**
   * Plays the clip-on entrance animation once, then settles into the static
   * end state. When false (default), renders the static end state directly.
   * Reduced-motion users always get the static end state regardless of this
   * flag — see docs/brand/ANIMATION.md § Reduced-motion handling.
   */
  animated?: boolean;
  /**
   * Surface hint. Light surface → slate ink + amber-500 accent; dark surface
   * → near-white ink + amber-300 accent. Defaults to `"light"`.
   */
  surface?: "light" | "dark";
  className?: string;
}

const PALETTES = {
  light: { ink: "#0F172A", accent: "#F59E0B" },
  dark: { ink: "#F8FAFC", accent: "#FBBF24" },
} as const;

const CONTAINER_HEIGHT = 56;
const CLIP_HEIGHT = 56;
const CLIP_WIDTH = 40;

const ENTRANCE_INITIAL = { y: -72, rotate: -32, opacity: 0 };
const ENTRANCE_ANIMATE = { y: 0, rotate: [-32, -10, -15], opacity: 1 };
const STATIC_END_STATE = { y: 0, rotate: -15, opacity: 1 };

const ENTRANCE_TRANSITION = {
  opacity: { duration: 0.3, delay: 0.2 },
  y: { duration: 0.3, delay: 0.2, ease: [0.16, 1, 0.3, 1] },
  rotate: {
    duration: 0.5,
    delay: 0.2,
    ease: [0.34, 1.56, 0.64, 1],
    times: [0, 0.6, 1],
  },
};

const HOVER_WIGGLE = {
  rotate: [-15, -13, -17, -15],
  transition: { duration: 0.32, ease: "easeInOut" as const },
};

/**
 * P5 clipped wordmark composition (the metaphor finally lands): the parent
 * paperclip mark gripping the top-left corner of "Paperwork Labs". Use only
 * on parent surfaces where the brand can shine — paperworklabs.com header,
 * Studio admin sidebar entrance, founder-mode hero, app load splash, OG
 * cards, footer attribution, business cards, press-kit interior, email
 * signature.
 *
 * NEVER use as a favicon — clip detail dies under 24 px. Use VerticalMark
 * (P2) instead.
 *
 * Spec:
 *   - Geometry / palette: docs/brand/PROMPTS.md § P5 + § Composition rules
 *   - Motion + reduced-motion: docs/brand/ANIMATION.md § "Tier 1 — Animated"
 *   - Brand grammar: .cursor/rules/brand.mdc § Visual grammar #4
 *
 * The component renders Wordmark (mid layer) and ClipMark (top layer) in a
 * relative container; surface palette is exposed via the `--pwl-clip-accent`
 * CSS custom property so ClipMark's inner amber span flips amber-500 →
 * amber-300 on dark surfaces without re-rendering the SVG.
 *
 * The clip-back portion (the part of the wire that should appear to wrap
 * "behind" the wordmark) is intentionally NOT drawn in v1 — see the TODO in
 * apps/studio/public/brand/paperwork-labs/paperclip/clipped-wordmark.svg. Acceptable per
 * PROMPTS.md fallback; the visible composition still reads correctly because
 * the clip-front sits in front of the cap-line.
 */
export function ClippedWordmark({
  animated = false,
  surface = "light",
  className,
}: ClippedWordmarkProps): React.ReactElement {
  const reduce = useReducedMotion();
  const playEntrance = animated && !reduce;
  const palette = PALETTES[surface];

  const containerStyle: React.CSSProperties = {
    position: "relative",
    display: "inline-block",
    height: CONTAINER_HEIGHT,
    color: palette.ink,
    paddingLeft: CLIP_WIDTH * 0.4,
    paddingTop: 8,
    // CSS custom property consumed by ClipMark for its amber span. Cast to
    // any because React's CSSProperties type does not allow `--*` keys
    // without a type assertion.
    ["--pwl-clip-accent" as never]: palette.accent,
  };

  const wordmarkSpanStyle: React.CSSProperties = {
    display: "inline-block",
    height: "100%",
  };

  const wordmarkSvgStyle: React.CSSProperties = {
    display: "block",
    height: "100%",
    width: "auto",
  };

  const clipSpanStyle: React.CSSProperties = {
    position: "absolute",
    top: -8,
    left: -4,
    width: CLIP_WIDTH,
    height: CLIP_HEIGHT,
    transformOrigin: "bottom right",
    pointerEvents: playEntrance ? "auto" : "none",
  };

  const clipSvgStyle: React.CSSProperties = {
    display: "block",
    width: "100%",
    height: "100%",
  };

  return (
    <div
      role="img"
      aria-label="Paperwork Labs"
      data-pwl-clipped-wordmark
      data-animated={playEntrance ? "true" : "false"}
      data-reduced-motion={reduce ? "true" : "false"}
      data-surface={surface}
      className={className}
      style={containerStyle}
    >
      <motion.span
        style={wordmarkSpanStyle}
        initial={playEntrance ? { opacity: 0 } : false}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <Wordmark style={wordmarkSvgStyle} />
      </motion.span>
      <motion.span
        aria-hidden
        style={clipSpanStyle}
        initial={playEntrance ? ENTRANCE_INITIAL : STATIC_END_STATE}
        animate={playEntrance ? ENTRANCE_ANIMATE : STATIC_END_STATE}
        transition={playEntrance ? ENTRANCE_TRANSITION : { duration: 0 }}
        whileHover={playEntrance ? HOVER_WIGGLE : undefined}
      >
        <ClipMark style={clipSvgStyle} />
      </motion.span>
    </div>
  );
}

export default ClippedWordmark;
