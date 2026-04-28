import * as React from "react";

export interface ClipMarkProps {
  /**
   * Optional class applied to the root svg. Sizing is up to the caller; the
   * SVG ships with viewBox="0 0 128 128" and no width/height so consumers
   * can size with Tailwind (`w-12 h-12`), inline style, or a parent wrapper.
   */
  className?: string;
  /** Inline style applied to the root svg (e.g., width/height). */
  style?: React.CSSProperties;
}

/**
 * P1 paperclip mark in NEUTRAL orientation (axis tilt 0°).
 *
 * Renders the canonical Gem-style continuous-wire paperclip with the parent's
 * continuous-extended amber span across the inner U-bend curve and the
 * adjacent inner straight wire below it (~1/6 to 1/4 of total perimeter).
 * Slate strokes use `currentColor` so callers can flip light/dark via the
 * parent's `color`; amber reads from `var(--pwl-clip-accent)` with a
 * hard-coded fallback to amber-500 (#F59E0B).
 *
 * Rotation is intentionally NOT baked in — `ClippedWordmark` wraps this in a
 * Framer Motion span that animates rotation from -32deg to -15deg per
 * docs/brand/ANIMATION.md. Standalone diagonal use cases should consume the
 * locked raster at `apps/studio/public/brand/renders/paperclip-LOCKED-canonical-1024.png`
 * (via `next/image`) instead of rotating this component.
 *
 * Spec: docs/brand/PROMPTS.md § P1 + § Composition rules.
 */
export function ClipMark({ className, style }: ClipMarkProps): React.ReactElement {
  return (
    <svg
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Paperwork Labs paperclip"
      className={className}
      style={style}
    >
      <title>Paperwork Labs paperclip</title>
      <path
        d="M 80 18 L 80 24 A 16 16 0 0 1 96 40 L 96 88 A 24 24 0 0 1 72 112 L 56 112 A 24 24 0 0 1 32 88 L 32 40 A 16 16 0 0 1 48 24 L 64 24 M 72 88 A 8 8 0 0 1 64 96 L 48 96"
        stroke="currentColor"
        strokeWidth={11}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M 64 24 A 8 8 0 0 1 72 32 L 72 88"
        stroke="var(--pwl-clip-accent, #F59E0B)"
        strokeWidth={11}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

export default ClipMark;
