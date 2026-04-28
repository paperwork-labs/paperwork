"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight } from "lucide-react";

import { Button } from "@paperwork-labs/ui";
import { fadeIn, slideInUp } from "@/lib/motion";

const PUNCHLINES = [
  "make you cry.",
  "cost $89.",
  "take 3 hours.",
  "feel this hard.",
  "require a CPA.",
] as const;

const CYCLE_MS = 4000;

function RotatingPunchline() {
  const [index, setIndex] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) =>
      setPrefersReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const advance = useCallback(() => {
    setIndex((prev) => (prev + 1) % PUNCHLINES.length);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) return;
    const id = setInterval(advance, CYCLE_MS);
    return () => clearInterval(id);
  }, [prefersReducedMotion, advance]);

  if (prefersReducedMotion) {
    return (
      <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
        {PUNCHLINES[0]}
      </span>
    );
  }

  return (
    <span className="inline-block h-[1.2em] overflow-hidden align-bottom">
      <AnimatePresence mode="wait">
        <motion.span
          key={PUNCHLINES[index]}
          className="inline-block bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
        >
          {PUNCHLINES[index]}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function Hero() {
  return (
    <section className="relative flex min-h-[90vh] flex-col items-center justify-center overflow-hidden px-4 pt-10 pb-20">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(263_70%_50%/0.15),transparent_70%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(238_76%_57%/0.1),transparent_60%)]" />

      <motion.div
        className="relative z-10 mx-auto flex max-w-2xl flex-col items-center text-center"
        initial="hidden"
        animate="visible"
        variants={fadeIn}
      >
        <motion.h1
          className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl md:text-6xl"
          variants={slideInUp}
        >
          Taxes shouldn&apos;t
          <br />
          <RotatingPunchline />
        </motion.h1>

        <motion.p
          className="mt-6 max-w-lg text-lg text-muted-foreground md:text-xl"
          variants={slideInUp}
        >
          Snap your W-2. Get your return in minutes. Actually free &mdash; no
          upsells, no hidden fees, no tricks.
        </motion.p>

        <motion.div className="mt-10 flex flex-col items-center gap-4" variants={slideInUp}>
          <Button
            asChild
            size="lg"
            className="h-12 bg-gradient-to-r from-violet-600 to-purple-600 px-8 text-base font-semibold hover:from-violet-500 hover:to-purple-500"
          >
            <Link href="/sign-up">
              Get Started Free
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>

          <p className="text-xs text-muted-foreground/60">
            Free forever. No credit card needed.
          </p>
        </motion.div>

        <motion.div className="mt-6" variants={slideInUp}>
          <Link
            href="/demo"
            className="text-sm font-medium text-violet-400 transition hover:text-violet-300"
          >
            Or try it now &mdash; snap your W-2, no account needed &rarr;
          </Link>
        </motion.div>
      </motion.div>
    </section>
  );
}
