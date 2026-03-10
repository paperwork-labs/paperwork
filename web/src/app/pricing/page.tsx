import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "FileFree is free. Federal and state tax filing, W-2 scanning, AI-powered extraction — all free, forever. No hidden fees.",
};

const freeFeatures = [
  "Federal tax return (1040)",
  "State tax return",
  "AI-powered W-2 scanning",
  "Automatic field extraction",
  "Refund/owed calculation",
  "PDF download",
  "Bank-level encryption",
  "Data deletion on request",
];

const comingSoon = [
  { name: "E-file direct to IRS", date: "January 2027" },
  { name: "AI tax advisor chat", date: "Coming soon" },
  { name: "Prior year comparison", date: "Coming soon" },
  { name: "Multi-state support", date: "Coming soon" },
];

export default function PricingPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: "FileFree Tax Filing",
    description: "Free AI-powered tax filing for everyone.",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      availability: "https://schema.org/InStock",
    },
  };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="mx-auto max-w-3xl px-4 py-16">
        <Link
          href="/"
          className="mb-8 inline-block text-sm text-muted-foreground transition hover:text-foreground"
        >
          &larr; Back to FileFree
        </Link>

        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Free.{" "}
          <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
            Actually free.
          </span>
        </h1>

        <p className="mt-4 text-lg text-muted-foreground">
          No &ldquo;free tier&rdquo; that upgrades you halfway through. No
          hidden fees at the end. FileFree is free for everyone, every year.
        </p>

        <div className="mt-12 rounded-xl border border-border/50 p-8">
          <div className="flex items-baseline gap-2">
            <span className="text-5xl font-bold text-foreground">$0</span>
            <span className="text-muted-foreground">/forever</span>
          </div>

          <p className="mt-3 text-sm text-muted-foreground">
            Federal + state filing. No credit card required.
          </p>

          <ul className="mt-8 space-y-3">
            {freeFeatures.map((feature) => (
              <li key={feature} className="flex items-center gap-3 text-sm">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-violet-500">
                  &#10003;
                </span>
                <span className="text-foreground">{feature}</span>
              </li>
            ))}
          </ul>

          <Link
            href="/demo"
            className="mt-8 flex h-12 items-center justify-center rounded-lg bg-gradient-to-r from-violet-600 to-purple-600 px-8 text-sm font-semibold text-white transition hover:from-violet-500 hover:to-purple-500"
          >
            Try It Now &mdash; No Account Needed
          </Link>
        </div>

        <div className="mt-12">
          <h2 className="text-xl font-bold text-foreground">Coming Soon</h2>
          <div className="mt-4 space-y-3">
            {comingSoon.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between rounded-lg border border-border/30 bg-card/20 px-4 py-3 text-sm"
              >
                <span className="text-foreground">{item.name}</span>
                <span className="text-xs text-muted-foreground">{item.date}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-12">
          <h2 className="text-xl font-bold text-foreground">
            How is it free?
          </h2>
          <p className="mt-3 text-muted-foreground">
            Filing is our acquisition channel, not our product. We make money
            through optional financial products: high-yield savings account
            referrals for your refund, an annual Tax Optimization Plan ($29/yr),
            and affiliate partnerships. Filing will always be free.
          </p>
        </div>

        <div className="mt-12">
          <h2 className="text-xl font-bold text-foreground">
            Still have questions?
          </h2>
          <p className="mt-3 text-muted-foreground">
            Reach out at{" "}
            <a
              href="mailto:hello@filefree.tax"
              className="text-violet-400 hover:text-violet-300"
            >
              hello@filefree.tax
            </a>{" "}
            and we&apos;ll get back to you within 24 hours.
          </p>
        </div>
      </div>
    </main>
  );
}
