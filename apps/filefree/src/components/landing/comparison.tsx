"use client";

import { motion } from "framer-motion";
import { X, Check } from "lucide-react";
import { fadeIn } from "@/lib/motion";

const rows = [
  { label: "Federal filing", us: "Free", them: "$0 – $169" },
  { label: "State filing", us: "Free", them: "$0 – $64" },
  { label: "Hidden upsells", us: false, them: true },
  { label: "60+ confusing questions", us: false, them: true },
  { label: "AI-powered W-2 scanning", us: true, them: false },
  { label: "Data sold to third parties", us: false, them: true },
];

export function Comparison() {
  return (
    <section className="px-4 py-24">
      <div className="mx-auto max-w-2xl">
        <motion.h2
          className="text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl"
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.3 }}
        >
          Not another{" "}
          <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
            TurboTax
          </span>
        </motion.h2>
        <motion.p
          className="mt-4 text-center text-muted-foreground"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ delay: 0.1, duration: 0.3 }}
        >
          We built what tax software should have been all along.
        </motion.p>

        <motion.div
          className="mt-12 overflow-hidden rounded-xl border border-border/50"
          variants={fadeIn}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          <div className="grid grid-cols-3 border-b border-border/50 bg-card/50 px-4 py-3 text-sm font-medium">
            <span className="text-muted-foreground" />
            <span className="text-center text-violet-500">FileFree</span>
            <span className="text-center text-muted-foreground">Others</span>
          </div>
          {rows.map((row, i) => (
            <div
              key={row.label}
              className={`grid grid-cols-3 items-center px-4 py-3 text-sm ${
                i < rows.length - 1 ? "border-b border-border/50" : ""
              }`}
            >
              <span className="text-muted-foreground">{row.label}</span>
              <span className="flex justify-center">
                {typeof row.us === "string" ? (
                  <span className="font-medium text-foreground">{row.us}</span>
                ) : row.us ? (
                  <Check className="h-4 w-4 text-green-500" />
                ) : (
                  <X className="h-4 w-4 text-muted-foreground/40" />
                )}
              </span>
              <span className="flex justify-center">
                {typeof row.them === "string" ? (
                  <span className="text-muted-foreground">{row.them}</span>
                ) : row.them ? (
                  <Check className="h-4 w-4 text-muted-foreground/40" />
                ) : (
                  <X className="h-4 w-4 text-muted-foreground/40" />
                )}
              </span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
