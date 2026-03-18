"use client";

import { motion } from "framer-motion";
import { useReducedMotion } from "framer-motion";
import type { PropsWithChildren } from "react";

type FadeInProps = PropsWithChildren<{
  delay?: number;
  className?: string;
}>;

export function FadeIn({ delay = 0, className, children }: FadeInProps) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 8 }}
      animate={reduceMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0.15 : 0.3, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
