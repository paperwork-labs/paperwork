"use client";

import { type Variants } from "framer-motion";
import { useEffect, useState } from "react";

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.3, ease: "easeOut" } },
};

export const slideInRight: Variants = {
  hidden: { x: 20, opacity: 0 },
  visible: { x: 0, opacity: 1, transition: { duration: 0.3, ease: "easeOut" } },
};

export const slideInLeft: Variants = {
  hidden: { x: -20, opacity: 0 },
  visible: { x: 0, opacity: 1, transition: { duration: 0.3, ease: "easeOut" } },
};

export const slideInUp: Variants = {
  hidden: { y: 10, opacity: 0 },
  visible: { y: 0, opacity: 1, transition: { duration: 0.3, ease: "easeOut" } },
};

export const scaleIn: Variants = {
  hidden: { scale: 0.95, opacity: 0 },
  visible: { scale: 1, opacity: 1, transition: { duration: 0.2, ease: "easeOut" } },
};

export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.05, delayChildren: 0.1 },
  },
};

export const countUpSpring = {
  type: "spring" as const,
  stiffness: 100,
  damping: 20,
  mass: 1,
};

export function useReducedMotion(): boolean {
  const [prefersReduced, setPrefersReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReduced(mq.matches);

    const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return prefersReduced;
}
