"use client";

import { motion } from "framer-motion";
import { Camera, ScanText, FileDown } from "lucide-react";
import { staggerContainer, slideInUp } from "@/lib/motion";

const steps = [
  {
    icon: Camera,
    title: "Snap your W-2",
    description: "Take a photo or upload your W-2. That's all we need to start.",
  },
  {
    icon: ScanText,
    title: "AI reads every field",
    description:
      "Our AI extracts your data in seconds. Review it, confirm, done.",
  },
  {
    icon: FileDown,
    title: "Download your return",
    description:
      "Get your completed 1040 as a PDF. E-file coming January 2027.",
  },
];

export function HowItWorks() {
  return (
    <section className="px-4 py-24">
      <div className="mx-auto max-w-4xl">
        <motion.h2
          className="text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl"
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.3 }}
        >
          Photo to done in{" "}
          <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
            5 minutes
          </span>
        </motion.h2>

        <motion.div
          className="mt-16 grid gap-8 md:grid-cols-3"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {steps.map((step, i) => (
            <motion.div
              key={step.title}
              className="flex flex-col items-center text-center"
              variants={slideInUp}
            >
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-500">
                <step.icon className="h-7 w-7" />
              </div>
              <p className="mt-2 text-xs font-medium uppercase tracking-widest text-muted-foreground/60">
                Step {i + 1}
              </p>
              <h3 className="mt-3 text-lg font-semibold text-foreground">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {step.description}
              </p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
