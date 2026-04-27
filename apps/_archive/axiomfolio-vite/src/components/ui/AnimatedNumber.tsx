/**
 * AnimatedNumber — smoothly tween between numeric values for KPI displays.
 *
 * Uses a framer-motion spring under the hood so the number feels physical
 * (slight ease-out) rather than linearly interpolated. On reduced-motion
 * preference, the value snaps without animation.
 *
 * Always renders with tabular-nums so the width does not jitter as digits
 * change. Screen-reader users hear the final value (not intermediate
 * frames) via the `aria-label`.
 */
import * as React from "react";
import { useMotionValue, useSpring, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { DURATION } from "@/lib/motion";

const DEFAULT_FORMATTER = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 2,
});

const defaultFormat = (n: number): string => DEFAULT_FORMATTER.format(n);

export interface AnimatedNumberProps {
  value: number;
  /**
   * Custom formatter. Defaults to `Intl.NumberFormat` with
   * `maximumFractionDigits: 2`.
   */
  format?: (n: number) => string;
  /**
   * Tween duration in seconds. The implementation uses a spring so this is
   * a soft target rather than an exact wall-clock duration; defaults to
   * `DURATION.medium`.
   */
  duration?: number;
  className?: string;
  /**
   * Accessible label for screen readers. Announces the final value rather
   * than the intermediate animation frames. Defaults to the formatted
   * value.
   */
  ariaLabel?: string;
}

export function AnimatedNumber({
  value,
  format = defaultFormat,
  duration = DURATION.medium,
  className,
  ariaLabel,
}: AnimatedNumberProps) {
  const reduced = useReducedMotion();
  const motionValue = useMotionValue(value);

  // Spring config approximates the requested duration. Higher `duration`
  // → softer spring (lower stiffness, slightly higher damping ratio).
  // We keep the spec defaults (stiffness 120, damping 20) when `duration`
  // is at the default; otherwise scale linearly off `DURATION.medium`.
  const springConfig = React.useMemo(() => {
    if (reduced) {
      // Effectively no animation — large stiffness, critical damping.
      return { stiffness: 1000, damping: 100, restDelta: 0.01 };
    }
    const ratio = DURATION.medium / Math.max(duration, 0.05);
    return {
      stiffness: Math.round(120 * ratio),
      damping: 20,
      restDelta: 0.001,
    };
  }, [duration, reduced]);

  const spring = useSpring(motionValue, springConfig);

  const [displayed, setDisplayed] = React.useState<string>(() => format(value));

  // Drive the spring whenever the prop changes. On reduced motion we snap
  // both the underlying motion value and the displayed string so observers
  // never see an intermediate frame.
  React.useEffect(() => {
    if (reduced) {
      motionValue.jump(value);
      spring.jump(value);
      setDisplayed(format(value));
      return;
    }
    motionValue.set(value);
  }, [value, reduced, motionValue, spring, format]);

  // Subscribe to spring updates and re-format. The `unsub` cleanup ensures
  // we never call `setState` after unmount, so the displayed value can
  // never lag behind the latest prop (no ghost frames).
  React.useEffect(() => {
    const unsub = spring.on("change", (latest) => {
      setDisplayed(format(latest));
    });
    return unsub;
  }, [spring, format]);

  return (
    <span
      className={cn("num tabular-nums", className)}
      aria-label={ariaLabel ?? format(value)}
      data-testid="animated-number"
    >
      {displayed}
    </span>
  );
}
