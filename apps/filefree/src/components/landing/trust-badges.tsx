"use client";

import { motion } from "framer-motion";
import { ShieldCheck, Lock, Trash2 } from "lucide-react";
import { staggerContainer, slideInUp } from "@/lib/motion";

const badges = [
  {
    icon: Lock,
    title: "256-bit Encrypted",
    description: "Bank-level encryption on every piece of data you share.",
  },
  {
    icon: ShieldCheck,
    title: "We never sell your data",
    description:
      "Unlike TurboTax, we don't monetize your personal information. Ever.",
  },
  {
    icon: Trash2,
    title: "Deleted when you ask",
    description:
      "One click and your data is gone. No hoops, no 30-day waits.",
  },
];

export function TrustBadges() {
  return (
    <section className="border-y border-border/50 bg-card/30 px-4 py-24">
      <div className="mx-auto max-w-4xl">
        <motion.h2
          className="text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl"
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.3 }}
        >
          Your data is{" "}
          <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
            yours
          </span>
        </motion.h2>

        <motion.div
          className="mt-16 grid gap-8 md:grid-cols-3"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {badges.map((badge) => (
            <motion.div
              key={badge.title}
              className="flex flex-col items-center text-center"
              variants={slideInUp}
            >
              <div className="flex h-14 w-14 items-center justify-center rounded-full border border-border/50 bg-background text-violet-500">
                <badge.icon className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-foreground">
                {badge.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {badge.description}
              </p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
