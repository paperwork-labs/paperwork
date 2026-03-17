"use client";

import { motion } from "framer-motion";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@venture/ui";
import { fadeIn } from "@/lib/motion";

const faqs = [
  {
    question: "Is FileFree really free?",
    answer:
      "Yes. Federal and state filing are free, forever. No upsells, no hidden fees, no 'free to start, pay to file' bait-and-switch. We make money from optional premium services and financial product recommendations after you file — never from filing itself.",
  },
  {
    question: "How does the W-2 scanning work?",
    answer:
      "Take a photo of your W-2 or upload it. Our AI reads every field in seconds using enterprise-grade OCR, then maps the data to your tax return. You review it, confirm, and you're done.",
  },
  {
    question: "Is my data safe?",
    answer:
      "Your SSN is extracted locally and never sent to any AI service. All data is encrypted with 256-bit AES encryption. W-2 images are auto-deleted within 24 hours. You can delete all your data with one click, anytime.",
  },
  {
    question: "What tax situations does FileFree support?",
    answer:
      "Right now, we support simple W-2 returns with standard deduction — that covers about 70% of filers. We're adding support for 1099 income, itemized deductions, and dependents soon.",
  },
  {
    question: "Can I e-file through FileFree?",
    answer:
      "E-file is coming January 2027. Until then, you can download your completed 1040 as a PDF and file it through IRS Free File or by mail. We're going through IRS certification to make e-file free forever.",
  },
];

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

export const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: faqs.map((faq) => ({
    "@type": "Question",
    name: faq.question,
    acceptedAnswer: {
      "@type": "Answer",
      text: faq.answer,
    },
  })),
};
