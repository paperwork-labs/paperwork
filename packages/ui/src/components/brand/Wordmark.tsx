import * as React from "react";

export interface WordmarkProps {
  /**
   * Optional class applied to the root svg. Sizing is up to the caller; the
   * SVG ships with viewBox covering the wordmark bounding box and no
   * width/height so consumers can scale via Tailwind (`h-12 w-auto`) or
   * inline style.
   */
  className?: string;
  /** Inline style applied to the root svg (e.g., width/height). */
  style?: React.CSSProperties;
}

const WORDMARK_FONT_FAMILY =
  "'Inter Tight', Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

/**
 * "Paperwork Labs" wordmark in Inter Tight 600 (semibold), `letter-spacing:
 * -0.02em`. Color is inherited via `currentColor` so callers can flip
 * light-on-dark / dark-on-light from the parent.
 *
 * The SVG viewBox is sized for the bare wordmark (no clip, no padding).
 * The parent clipped lockup (paperclip + this wordmark) ships only as the
 * locked PNG (`apps/studio/public/brand/renders/paperclip-LOCKED-canonical-1024.png`)
 * consumed via `next/image` or `<img>` — see docs/brand/CANON.md. Canvas is
 * 1000 × 200 user units so cap-height lands near 120 (matches § Visual grammar).
 *
 * Spec: docs/brand/CANON.md § Visual grammar + .cursor/rules/brand.mdc (voice/copy).
 */
export function Wordmark({ className, style }: WordmarkProps): React.ReactElement {
  return (
    <svg
      viewBox="0 0 1000 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Paperwork Labs"
      className={className}
      style={style}
    >
      <title>Paperwork Labs</title>
      <text
        x={0}
        y={155}
        fill="currentColor"
        fontFamily={WORDMARK_FONT_FAMILY}
        fontWeight={600}
        fontSize={165}
        letterSpacing={-3.3}
      >
        Paperwork Labs
      </text>
    </svg>
  );
}

export default Wordmark;
