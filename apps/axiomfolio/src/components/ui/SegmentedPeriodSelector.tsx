/**
 * `SegmentedPeriodSelector` — iOS-style segmented control.
 *
 * The control renders as a WAI-ARIA radio group: each option is a
 * `role="radio"` button, the parent is `role="radiogroup"`, and arrow keys
 * both move focus AND change selection (the canonical pattern).
 *
 * Visual signature: a sliding pill behind the active segment that smoothly
 * tweens between options using framer-motion's `layoutId` (scoped per
 * instance via `React.useId()` so multiple selectors on the same page don't
 * cross-animate). Honors `useReducedMotion()` — when reduced, the indicator
 * snaps with no transition.
 */
import * as React from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { DURATION, EASE } from "@/lib/motion";

export interface SegmentedPeriodOption<V extends string = string> {
  value: V;
  label: string;
  ariaLabel?: string;
}

export interface SegmentedPeriodSelectorProps<V extends string = string> {
  options: ReadonlyArray<SegmentedPeriodOption<V>>;
  value: V;
  onChange: (value: V) => void;
  size?: "sm" | "md";
  className?: string;
  /** Required for screen-reader users — names the control (e.g. "Time period"). */
  ariaLabel: string;
}

const SIZE_CLASSES = {
  sm: {
    root: "h-7 p-0.5 text-[11px]",
    button: "h-6 px-2.5",
  },
  md: {
    root: "h-9 p-1 text-xs",
    button: "h-7 px-3.5",
  },
} as const;

export function SegmentedPeriodSelector<V extends string = string>({
  options,
  value,
  onChange,
  size = "md",
  className,
  ariaLabel,
}: SegmentedPeriodSelectorProps<V>) {
  const reactId = React.useId();
  const reducedMotion = useReducedMotion();
  const buttonRefs = React.useRef<Array<HTMLButtonElement | null>>([]);
  const sz = SIZE_CLASSES[size];

  // If the controlled `value` doesn't match any option (e.g. consumer is
  // still hydrating), fall back to index 0 so that one button still gets
  // tabIndex=0 and the radiogroup remains reachable via keyboard. We
  // deliberately do NOT mark that fallback button as `aria-checked` —
  // the radiogroup is simply in an "indeterminate selection" state until
  // the controlling parent settles on a real value.
  const matchedIndex = options.findIndex((o) => o.value === value);
  const activeIndex = matchedIndex < 0 ? 0 : matchedIndex;

  const focusAndSelect = React.useCallback(
    (index: number) => {
      if (index < 0 || index >= options.length) return;
      onChange(options[index].value);
      // Defer focus until after onChange has flushed so screen readers
      // announce the new active state once, not twice.
      requestAnimationFrame(() => {
        buttonRefs.current[index]?.focus();
      });
    },
    [onChange, options],
  );

  const onKeyDown = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const last = options.length - 1;
    let next: number | null = null;
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        next = index === last ? 0 : index + 1;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        next = index === 0 ? last : index - 1;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }
    e.preventDefault();
    focusAndSelect(next);
  };

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "relative inline-flex select-none items-center rounded-full bg-muted",
        sz.root,
        className,
      )}
    >
      {options.map((option, i) => {
        const isActive = option.value === value;
        // Tabbable index: the matched option, or index 0 as the fallback
        // when the controlled value isn't among `options`. This keeps the
        // group keyboard-reachable even in transient/loading states.
        const isTabbable = i === activeIndex;
        return (
          <button
            key={option.value}
            ref={(el) => {
              buttonRefs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={isActive}
            aria-label={option.ariaLabel ?? option.label}
            tabIndex={isTabbable ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              "relative z-10 inline-flex items-center justify-center rounded-full",
              "transition-colors duration-150",
              // Suppress the mouse-click outline only for non-keyboard
              // focus, so the global :focus-visible baseline still applies
              // to keyboard users. Add an explicit ring that matches the
              // design system for a polished focus state.
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              sz.button,
              isActive
                ? "font-medium text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <AnimatePresence initial={false}>
              {isActive && (
                <motion.span
                  layoutId={`segmented-indicator-${reactId}`}
                  className={cn(
                    "absolute inset-0 -z-10 rounded-full bg-background",
                    "shadow-[var(--shadow-resting)]",
                  )}
                  transition={
                    reducedMotion
                      ? { duration: 0 }
                      : { duration: DURATION.fast, ease: EASE.standard }
                  }
                  aria-hidden
                />
              )}
            </AnimatePresence>
            <span className="relative">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default SegmentedPeriodSelector;
