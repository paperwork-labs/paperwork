"use client";

import * as React from "react";

// TODO(brand/p5): replace this placeholder with the canonical SVG composition once
// the parallel `brand/p5-clipped-wordmark-svg` track lands. Spec lives in
// docs/brand/PROMPTS.md § P5 and the runtime motion in docs/brand/ANIMATION.md.
// This stub exists so packages/ui consumers + Ladle stories can wire to a stable
// import path today; the visible geometry will be replaced wholesale.

export interface ClippedWordmarkProps {
  /**
   * Plays the clip-on entrance animation once, then settles into the static
   * end state. When false (default), renders the static end state directly.
   * Reduced-motion users always get the static end state regardless of this
   * flag — see docs/brand/ANIMATION.md § Reduced-motion handling.
   */
  animated?: boolean;
  /**
   * Optional surface hint. Light surface → slate ink + amber accent; dark
   * surface → near-white ink + amber-300 accent. The component reads
   * `prefers-color-scheme` by default; pass an explicit value to override.
   */
  surface?: "light" | "dark";
  className?: string;
}

function useReducedMotion(): boolean {
  const [reduce, setReduce] = React.useState(false);
  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduce(mql.matches);
    const onChange = (event: MediaQueryListEvent) => setReduce(event.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return reduce;
}

/**
 * Placeholder for the P5 "clipped wordmark" composition.
 *
 * The shipping component (in flight on `brand/p5-clipped-wordmark-svg`) will
 * use framer-motion + the canonical SVG `ClipMark` and `Wordmark` siblings.
 * This stub renders a slate rectangle + amber dot + the literal "Paperwork
 * Labs" text so types and Ladle stories can be wired up today.
 */
export function ClippedWordmark({
  animated = false,
  surface,
  className,
}: ClippedWordmarkProps): React.ReactElement {
  const reduce = useReducedMotion();
  const playEntrance = animated && !reduce;

  const isDark = surface === "dark";
  const wordmarkColor = isDark ? "#F8FAFC" : "#0F172A";
  const accentColor = isDark ? "#FBBF24" : "#F59E0B";

  return (
    <div
      role="img"
      aria-label="Paperwork Labs"
      data-pwl-clipped-wordmark
      data-animated={playEntrance ? "true" : "false"}
      data-reduced-motion={reduce ? "true" : "false"}
      className={className}
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 16px 8px 24px",
        fontFamily:
          'InterTight, "Inter Tight", Inter, system-ui, -apple-system, sans-serif',
        fontWeight: 600,
        fontSize: 28,
        letterSpacing: "-0.02em",
        color: wordmarkColor,
        opacity: playEntrance ? 0 : 1,
        animation: playEntrance ? "pwl-stub-fade 200ms 0ms ease-out forwards" : undefined,
      }}
    >
      <span
        aria-hidden
        style={{
          position: "absolute",
          top: -8,
          left: 4,
          width: 18,
          height: 44,
          borderRadius: 4,
          background: wordmarkColor,
          transformOrigin: "bottom right",
          transform: playEntrance
            ? "translateY(-72px) rotate(-32deg)"
            : "rotate(-15deg)",
          animation: playEntrance
            ? "pwl-stub-clip-on 700ms 200ms cubic-bezier(0.16,1,0.3,1) both"
            : undefined,
        }}
      >
        <span
          aria-hidden
          style={{
            position: "absolute",
            inset: "auto 3px 6px auto",
            width: 6,
            height: 6,
            borderRadius: 999,
            background: accentColor,
          }}
        />
      </span>
      <style>{`
        @keyframes pwl-stub-clip-on {
          0%   { transform: translateY(-72px) rotate(-32deg); opacity: 0; }
          60%  { transform: translateY(0)     rotate(-10deg); opacity: 1; }
          100% { transform: translateY(0)     rotate(-15deg); opacity: 1; }
        }
        @keyframes pwl-stub-fade {
          0%   { opacity: 0; }
          100% { opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          [data-pwl-clipped-wordmark] { animation: none !important; opacity: 1 !important; }
          [data-pwl-clipped-wordmark] > span { animation: none !important; transform: rotate(-15deg) !important; }
        }
      `}</style>
      <span style={{ paddingLeft: 28 }}>Paperwork Labs</span>
    </div>
  );
}

export default ClippedWordmark;
