/**
 * `RichTooltip` — frosted-glass popover for content-heavy hover/click hints.
 *
 * Built on `@radix-ui/react-popover` (NOT `react-tooltip`) because the
 * content needs to be focusable and interactive — links, buttons, mini
 * charts. The simple text-only `Tooltip` primitive in `tooltip.tsx`
 * remains the right tool for plain labels.
 *
 * Open behavior:
 *   - `hover` (default): opens on pointer enter / focus, closes after an
 *     ~80ms debounce on leave/blur so the user can sweep into the popover
 *     without it disappearing.
 *   - `click`: standard click toggle.
 *   - `focus`: opens only on keyboard focus.
 *   - `controlled`: pass `open` + `onOpenChange` from a parent.
 *
 * Honors `useReducedMotion()` — when reduced, the open/close animation
 * collapses to opacity only.
 */
import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { DURATION, EASE, INSTANT, scaleIn } from "@/lib/motion";

type Side = "top" | "right" | "bottom" | "left";
type Align = "start" | "center" | "end";
type OpenOn = "hover" | "click" | "focus" | "controlled";

export interface RichTooltipProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  side?: Side;
  align?: Align;
  sideOffset?: number;
  openOn?: OpenOn;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  ariaLabel?: string;
  /** Max content width in px. Default 320. */
  maxWidth?: number;
  className?: string;
}

const HOVER_DEBOUNCE_MS = 80;

export function RichTooltip({
  trigger,
  children,
  side = "top",
  align = "center",
  sideOffset = 6,
  openOn = "hover",
  open: openProp,
  onOpenChange,
  ariaLabel,
  maxWidth = 320,
  className,
}: RichTooltipProps) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const reducedMotion = useReducedMotion();
  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const isControlled = openOn === "controlled" || openProp !== undefined;
  const open = isControlled ? Boolean(openProp) : internalOpen;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  const cancelClose = React.useCallback(() => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);

  const scheduleClose = React.useCallback(() => {
    cancelClose();
    closeTimer.current = setTimeout(() => {
      setOpen(false);
      closeTimer.current = null;
    }, HOVER_DEBOUNCE_MS);
  }, [cancelClose, setOpen]);

  React.useEffect(() => {
    return () => {
      if (closeTimer.current) clearTimeout(closeTimer.current);
    };
  }, []);

  // Track whether focus is inside the trigger or the popover content. We
  // use this to decide whether a `focusout` should close the popover, so
  // tabbing from trigger -> popover content (or back) keeps it open.
  const triggerWrapperRef = React.useRef<HTMLSpanElement | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  const isInsideOurUI = React.useCallback((node: Node | null): boolean => {
    if (!node) return false;
    const trig = triggerWrapperRef.current;
    const cont = contentRef.current;
    return Boolean(
      (trig && trig.contains(node)) || (cont && cont.contains(node)),
    );
  }, []);

  const handleFocusOut = React.useCallback(
    (e: React.FocusEvent) => {
      if (openOn !== "hover" && openOn !== "focus") return;
      // `relatedTarget` is the element receiving focus. If it's still inside
      // our trigger or content, treat it as an internal focus move and keep
      // the popover open.
      const next = e.relatedTarget as Node | null;
      if (isInsideOurUI(next)) {
        cancelClose();
        return;
      }
      scheduleClose();
    },
    [cancelClose, isInsideOurUI, openOn, scheduleClose],
  );

  const handleFocusIn = React.useCallback(
    (_e: React.FocusEvent) => {
      if (openOn !== "hover" && openOn !== "focus") return;
      cancelClose();
      setOpen(true);
    },
    [cancelClose, openOn, setOpen],
  );

  const triggerHandlers: React.HTMLAttributes<HTMLSpanElement> = {};
  if (openOn === "hover") {
    triggerHandlers.onPointerEnter = () => {
      cancelClose();
      setOpen(true);
    };
    triggerHandlers.onPointerLeave = scheduleClose;
    triggerHandlers.onFocus = handleFocusIn;
    triggerHandlers.onBlur = handleFocusOut;
  } else if (openOn === "focus") {
    triggerHandlers.onFocus = handleFocusIn;
    triggerHandlers.onBlur = handleFocusOut;
  }

  // ARIA role:
  //   - For interactive content (we always allow children to be focusable),
  //     `role="tooltip"` is incorrect. When the consumer provides an
  //     `ariaLabel`, expose the popover as a non-modal `dialog`.
  //   - With no ariaLabel, leave the role unset and let Radix Popover's
  //     default ARIA semantics apply.
  const contentRole = ariaLabel ? "dialog" : undefined;

  // For controlled mode, let the parent drive Popover.Root; otherwise we
  // manage state explicitly so click/hover behaviors compose cleanly.
  return (
    <PopoverPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        // ALWAYS honor a close request from Radix (Escape, click-outside,
        // etc.) regardless of `openOn` — otherwise hover/focus popovers
        // become impossible to dismiss with the keyboard.
        if (!next) {
          setOpen(false);
          return;
        }
        // Open requests are still gated by mode so click-driven popovers
        // don't pop on hover and vice versa.
        if (openOn === "click" || openOn === "controlled") {
          setOpen(true);
        }
      }}
    >
      <PopoverPrimitive.Trigger asChild>
        <span
          {...triggerHandlers}
          ref={triggerWrapperRef}
          // Inline-block ensures pointer events register on the wrapper
          // even when the trigger child is a fragment-like atom.
          className="inline-flex"
          data-state={open ? "open" : "closed"}
        >
          {trigger}
        </span>
      </PopoverPrimitive.Trigger>

      <AnimatePresence>
        {open ? (
          <PopoverPrimitive.Portal forceMount>
            <PopoverPrimitive.Content
              forceMount
              ref={contentRef}
              side={side}
              align={align}
              sideOffset={sideOffset}
              onPointerEnter={openOn === "hover" ? cancelClose : undefined}
              onPointerLeave={openOn === "hover" ? scheduleClose : undefined}
              // Focus tracking on the content lets us distinguish "user
              // Tabbed back out of the popover" (close) from "user Tabbed
              // between two interactive elements inside it" (no-op). The
              // relatedTarget check inside `handleFocusOut` handles both.
              onFocus={
                openOn === "hover" || openOn === "focus"
                  ? handleFocusIn
                  : undefined
              }
              onBlur={
                openOn === "hover" || openOn === "focus"
                  ? handleFocusOut
                  : undefined
              }
              className={cn(
                "z-50 rounded-md border border-border/60 bg-popover/85 p-3",
                "text-popover-foreground backdrop-blur-md",
                "shadow-[var(--shadow-floating)]",
                "outline-none",
                className,
              )}
              style={{ maxWidth }}
              role={contentRole}
              aria-label={ariaLabel}
              aria-modal={contentRole === "dialog" ? false : undefined}
            >
              <motion.div
                variants={reducedMotion ? INSTANT : scaleIn}
                initial="hidden"
                animate="visible"
                exit="exit"
                transition={
                  reducedMotion
                    ? { duration: 0 }
                    : { duration: DURATION.fast, ease: EASE.standard }
                }
              >
                {children}
              </motion.div>
              <PopoverPrimitive.Arrow
                className="fill-popover/85 drop-shadow-sm"
                width={10}
                height={5}
              />
            </PopoverPrimitive.Content>
          </PopoverPrimitive.Portal>
        ) : null}
      </AnimatePresence>
    </PopoverPrimitive.Root>
  );
}

export default RichTooltip;
