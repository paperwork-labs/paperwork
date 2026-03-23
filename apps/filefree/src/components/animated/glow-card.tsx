"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { PropsWithChildren } from "react";

type GlowCardProps = PropsWithChildren<{
  className?: string;
}>;

export function GlowCard({ className, children }: GlowCardProps) {
  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "rounded-xl border border-border/80 bg-card/60 p-4 shadow-brand",
        className
      )}
    >
      {children}
    </motion.div>
  );
}
