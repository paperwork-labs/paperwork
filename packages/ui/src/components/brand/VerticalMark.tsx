import * as React from "react";

export interface VerticalMarkProps {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * P2 paperclip mark in strictly VERTICAL orientation (axis tilt 0°).
 *
 * Canonical favicon and app-icon glyph. Slate strokes use `currentColor`;
 * amber reads from `var(--pwl-clip-accent)` with a fallback to amber-500 (#F59E0B).
 *
 * Spec: docs/brand/PROMPTS.md § P2 + § Composition rules.
 */
export function VerticalMark({ className, style }: VerticalMarkProps): React.ReactElement {
  return (
    <svg
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Paperwork Labs paperclip mark"
      className={className}
      style={style}
    >
      <title>Paperwork Labs paperclip mark</title>
      <path
        d="M 80 18 L 80 24 A 16 16 0 0 1 96 40"
        stroke="currentColor"
        strokeWidth={11}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M 96 40 L 96 88 A 24 24 0 0 1 72 112"
        stroke="var(--pwl-clip-accent, #F59E0B)"
        strokeWidth={11}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M 72 112 L 56 112 A 24 24 0 0 1 32 88 L 32 40 A 16 16 0 0 1 48 24 L 64 24 M 72 88 A 8 8 0 0 1 64 96 L 48 96"
        stroke="currentColor"
        strokeWidth={11}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M 64 24 A 8 8 0 0 1 72 32 L 72 88"
        stroke="currentColor"
        strokeWidth={11}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

export default VerticalMark;
