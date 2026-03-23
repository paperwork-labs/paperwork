"use client";

import { motion } from "framer-motion";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@paperwork-labs/ui";
import { fadeIn } from "@/lib/motion";
import { faqs } from "./faq-data";

export function FAQ() {
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
          Questions?{" "}
          <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
            Answered.
          </span>
        </motion.h2>

        <motion.div
          className="mt-12"
          variants={fadeIn}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          <Accordion type="single" collapsible className="w-full">
            {faqs.map((faq, i) => (
              <AccordionItem key={i} value={`item-${i}`}>
                <AccordionTrigger className="text-left text-base font-medium">
                  {faq.question}
                </AccordionTrigger>
                <AccordionContent className="text-sm leading-relaxed text-muted-foreground">
                  {faq.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </motion.div>
      </div>
    </section>
  );
}
