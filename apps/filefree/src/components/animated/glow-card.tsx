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
        "rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.03),0_12px_40px_rgba(124,58,237,0.15)]",
        className
      )}
    >
      {children}
    </motion.div>
  );
}
