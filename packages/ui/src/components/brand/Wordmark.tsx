import * as React from "react";

export interface WordmarkProps {
  className?: string;
  style?: React.CSSProperties;
}

const WORDMARK_FONT_FAMILY =
  "'Inter Tight', Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

/**
 * "Paperwork Labs" wordmark in Inter Tight 600 (semibold), `letter-spacing:
 * -0.02em`. Color is inherited via `currentColor`.
 *
 * Spec: docs/brand/PROMPTS.md § Composition rules + .cursor/rules/brand.mdc
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
