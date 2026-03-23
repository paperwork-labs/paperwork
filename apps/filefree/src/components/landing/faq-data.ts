export const faqs = [
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
