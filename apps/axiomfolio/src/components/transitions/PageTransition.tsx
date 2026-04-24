/**
 * PageTransition — wraps page content with a subtle slide-up + fade entry.
 *
 * The consumer is responsible for installing `<AnimatePresence mode="wait">`
 * around the route layer (since route layouts vary per app), and for
 * passing a stable `key` so AnimatePresence can detect page swaps.
 *
 * On reduced-motion preference, the slide is dropped and only a brief
 * opacity fade remains so the page change is still announced visually
 * without movement.
 */
import * as React from "react";
import { LayoutGroup, motion, useReducedMotion, type Variants } from "framer-motion";

import { slideUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface PageTransitionProps {
  children: React.ReactNode;
  className?: string;
}

const REDUCED_VARIANTS: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.12 } },
  exit: { opacity: 0, transition: { duration: 0.08 } },
};

export function PageTransition({ children, className }: PageTransitionProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      data-testid="page-transition"
      className={cn(className)}
      variants={reduced ? REDUCED_VARIANTS : slideUp}
      initial="hidden"
      animate="visible"
      exit="exit"
    >
      {children}
    </motion.div>
  );
}

export interface SharedLayoutGroupProps {
  /** Stable identifier — required for cross-page shared element transitions. */
  id: string;
  children: React.ReactNode;
}

/**
 * Thin wrapper around framer-motion's `LayoutGroup`, used to share layout
 * IDs (`layoutId="..."`) across page boundaries so elements can morph
 * between routes (e.g. a card on the list view expanding into the detail
 * view's header).
 */
export function SharedLayoutGroup({ id, children }: SharedLayoutGroupProps) {
  return <LayoutGroup id={id}>{children}</LayoutGroup>;
}
