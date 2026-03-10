"use client";

import { motion } from "framer-motion";
import { Calculator } from "lucide-react";

import { slideInUp } from "@/lib/motion";

export default function SummaryPage() {
  return (
    <motion.div
      className="flex min-h-[50vh] flex-col items-center justify-center text-center"
      initial="hidden"
      animate="visible"
      variants={slideInUp}
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-600/20">
        <Calculator className="h-8 w-8 text-violet-400" />
      </div>
      <h2 className="mt-4 text-2xl font-bold text-foreground">
        Return summary coming soon
      </h2>
      <p className="mt-2 max-w-md text-muted-foreground">
        The tax calculator and return summary will be built in the next
        sprint. Your data has been saved.
      </p>
    </motion.div>
  );
}
