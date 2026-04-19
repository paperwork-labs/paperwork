import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * `ChartGlassCard` — the canonical frame for any flagship chart surface.
 *
 * Why this exists: Recharts and lightweight-charts both render onto a plain
 * canvas/SVG element. Wrapping them in a consistent, premium-feeling frame
 * is what separates a quant tool from a dashboard. This component encodes:
 *   - Layered depth via the `--shadow-*` elevation scale (light + dark tuned).
 *   - A 1px inset highlight on dark mode (the trick every premium UI uses
 *     to keep glass surfaces from looking flat against pure black).
 *   - Optional frosted backdrop blur for cards floating above content.
 *   - Predictable padding + radius so multiple charts on the same page line
 *     up without ad-hoc spacing.
 *
 * Levels (resting / hover / active / floating) map to physical metaphors:
 *   - resting: in-flow content card
 *   - hover:   feedback when the user is interacting with chart
 *   - active:  modal-adjacent surfaces
 *   - floating: detached overlays (share preview, OG generator)
 */
const chartGlassCardVariants = cva(
  // Base — every card gets these. The inset ring + bg-card stack gives the
  // characteristic "two-layer glass" look that survives both themes.
  cn(
    "relative isolate flex flex-col overflow-hidden",
    "rounded-2xl bg-card text-card-foreground",
    "ring-1 ring-foreground/[0.06] dark:ring-white/[0.08]",
    // Dark-mode inset highlight along the top edge — the secret sauce.
    "dark:before:pointer-events-none dark:before:absolute dark:before:inset-x-0 dark:before:top-0",
    "dark:before:h-px dark:before:bg-gradient-to-r",
    "dark:before:from-transparent dark:before:via-white/10 dark:before:to-transparent",
  ),
  {
    variants: {
      level: {
        resting: "shadow-[var(--shadow-resting)]",
        hover: "shadow-[var(--shadow-hover)]",
        active: "shadow-[var(--shadow-active)]",
        floating: "shadow-[var(--shadow-floating)]",
      },
      glass: {
        true: "backdrop-blur-xl bg-card/85 supports-[backdrop-filter]:bg-card/70",
        false: "",
      },
      interactive: {
        true: cn(
          "transition-shadow duration-300 ease-out",
          "hover:shadow-[var(--shadow-hover)]",
          "focus-within:shadow-[var(--shadow-hover)]",
        ),
        false: "",
      },
      padding: {
        none: "",
        sm: "p-4",
        md: "p-6",
        lg: "p-8",
      },
    },
    defaultVariants: {
      level: "resting",
      glass: false,
      interactive: false,
      padding: "md",
    },
  },
);

export interface ChartGlassCardProps
  extends React.HTMLAttributes<HTMLElement>,
    VariantProps<typeof chartGlassCardVariants> {
  /**
   * Optional label exposed to assistive tech describing the chart contents.
   * If a caller-supplied `aria-label` is also passed via spread, it takes
   * precedence (we intentionally let consumers override).
   */
  ariaLabel?: string;
  /**
   * Render as a different intrinsic element (e.g., `as="section"`). We keep
   * the API intentionally narrow (intrinsic tags only — no polymorphic
   * component support) to avoid the well-known generics gymnastics that come
   * with full polymorphism while still covering the common cases.
   */
  as?: "div" | "section" | "article" | "aside" | "figure";
}

const ChartGlassCard = React.forwardRef<HTMLElement, ChartGlassCardProps>(
  function ChartGlassCard(
    {
      className,
      level,
      glass,
      interactive,
      padding,
      ariaLabel,
      as = "div",
      ...props
    },
    ref,
  ) {
    // Caller-supplied aria-label wins over the convenience `ariaLabel` prop.
    // We resolve role from the *effective* label so the `role="region"` is
    // dropped when the consumer explicitly clears the label via spread.
    const effectiveAriaLabel =
      (props as { "aria-label"?: string })["aria-label"] ?? ariaLabel;

    return React.createElement(as, {
      ref,
      "data-slot": "chart-glass-card",
      "data-level": level ?? "resting",
      "data-glass": glass ? "true" : undefined,
      "aria-label": effectiveAriaLabel,
      role: effectiveAriaLabel ? "region" : undefined,
      ...props,
      className: cn(
        chartGlassCardVariants({ level, glass, interactive, padding }),
        className,
      ),
    });
  },
);

export { ChartGlassCard, chartGlassCardVariants };
