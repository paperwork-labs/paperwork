"use client";

import { motion } from "framer-motion";

export function TypingDots() {
  return (
    <div className="inline-flex items-center gap-1 align-middle">
      {[0, 1, 2].map((dot) => (
        <motion.span
          // Stable index keys are fine for static decorative elements.
          key={dot}
          className="h-1.5 w-1.5 rounded-full bg-violet-400"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1, repeat: Number.POSITIVE_INFINITY, delay: dot * 0.2 }}
        />
      ))}
    </div>
  );
}
