import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "How to File Your Taxes for Free in 2026 — FileFree",
  description:
    "A complete guide to filing your federal and state taxes for free in 2026. Compare IRS Free File, Direct File, VITA, and other free options to find the best fit.",
  keywords: [
    "how to file taxes for free 2026",
    "free tax filing",
    "IRS Free File",
    "free tax return",
  ],
};

const faqItems = [
  {
    question: "Can I really file my taxes for free?",
    answer:
      "Yes. The IRS offers Free File for filers with AGI under $84,000, and Direct File is available in participating states. VITA provides free in-person help. Several private apps, including FileFree, also offer completely free federal and state filing with no income cap.",
  },
  {
    question: "What is the income limit for IRS Free File in 2026?",
    answer:
      "For the 2025 tax year (filed in 2026), IRS Free File is available to taxpayers with an adjusted gross income (AGI) of $84,000 or less. Free File Fillable Forms have no income limit but offer no guided help.",
  },
  {
    question: "Is free tax software safe to use?",
    answer:
      "Reputable free tax software uses bank-level encryption (TLS in transit, AES-256 at rest) to protect your data. Check that the provider is an IRS-authorized e-file provider, read their privacy policy, and confirm they do not sell your data to third parties.",
  },
  {
    question:
      "What is the difference between IRS Free File and Free File Fillable Forms?",
    answer:
      "IRS Free File partners offer guided, interview-style software but have income limits. Free File Fillable Forms are essentially digital versions of blank IRS forms — no guidance, no income limit. Most filers prefer guided software.",
  },
];

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: faqItems.map((item) => ({
    "@type": "Question",
    name: item.question,
    acceptedAnswer: {
      "@type": "Answer",
      text: item.answer,
    },
  })),
};

export default function HowToFileTaxesForFreePage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <article className="mx-auto max-w-3xl px-4 py-16">
        <Link
          href="/"
          className="text-sm text-muted-foreground transition hover:text-foreground"
        >
          &larr; Back to FileFree
        </Link>

        <h1 className="mt-8 text-3xl font-bold tracking-tight md:text-4xl">
          How to File Your Taxes for Free in 2026
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          You should never have to pay to file a simple tax return. Here are all
          the legitimate ways to file your federal (and often state) taxes for
          $0 in 2026.
        </p>

        <div className="mt-12 space-y-10 text-lg leading-relaxed text-muted-foreground">
          {/* IRS Free File */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              1. IRS Free File Program
            </h2>
            <p className="mt-3">
              The IRS partners with private tax software companies to offer free
              guided tax preparation to filers with an adjusted gross income
              (AGI) of <strong className="text-foreground">$84,000 or less</strong>.
              You choose from a list of participating providers on{" "}
              <a
                href="https://www.irs.gov/filing/free-file-do-your-federal-taxes-for-free"
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-400 underline decoration-violet-400/30 hover:decoration-violet-400"
              >
                IRS.gov/freefile
              </a>
              , and each provider may have its own additional restrictions
              (age, state, military status, etc.).
            </p>
            <p className="mt-3">
              If your AGI is above $84,000, you can still use{" "}
              <strong className="text-foreground">
                Free File Fillable Forms
              </strong>{" "}
              — essentially blank digital IRS forms with basic math assistance
              but no guided interview.
            </p>
          </section>

          {/* IRS Direct File */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              2. IRS Direct File
            </h2>
            <p className="mt-3">
              The IRS launched Direct File as a pilot in 2024 and has been
              expanding it since. Direct File lets you prepare and e-file your
              federal return directly with the IRS at no cost and with no
              third-party involvement. It works best for straightforward returns
              (W-2 income, standard deduction) and is currently available in
              select states.
            </p>
            <p className="mt-3">
              Check{" "}
              <a
                href="https://directfile.irs.gov"
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-400 underline decoration-violet-400/30 hover:decoration-violet-400"
              >
                directfile.irs.gov
              </a>{" "}
              to see if your state participates for the 2025 filing season.
            </p>
          </section>

          {/* VITA */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              3. VITA &amp; TCE (Free In-Person Help)
            </h2>
            <p className="mt-3">
              The{" "}
              <strong className="text-foreground">
                Volunteer Income Tax Assistance (VITA)
              </strong>{" "}
              program offers free tax preparation at community centers,
              libraries, and colleges. VITA is available to filers who earn
              $67,000 or less, people with disabilities, and limited
              English-speaking taxpayers.
            </p>
            <p className="mt-3">
              The{" "}
              <strong className="text-foreground">
                Tax Counseling for the Elderly (TCE)
              </strong>{" "}
              program focuses on filers age 60 and older and specializes in
              pension and retirement-related questions.
            </p>
            <p className="mt-3">
              Use the{" "}
              <a
                href="https://irs.treasury.gov/freetaxprep/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-400 underline decoration-violet-400/30 hover:decoration-violet-400"
              >
                IRS VITA locator tool
              </a>{" "}
              to find a site near you.
            </p>
          </section>

          {/* FreeTaxUSA */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              4. FreeTaxUSA
            </h2>
            <p className="mt-3">
              FreeTaxUSA offers free federal filing for all income levels with a
              guided interview. State returns cost $14.99. It supports most
              common forms and schedules, making it a solid choice if you
              don&apos;t mind paying a small fee for state filing. No income cap
              on the free federal return.
            </p>
          </section>

          {/* FileFree */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              5. FileFree — AI-Powered, Free Forever
            </h2>
            <p className="mt-3">
              <Link
                href="/"
                className="text-violet-400 underline decoration-violet-400/30 hover:decoration-violet-400"
              >
                FileFree
              </Link>{" "}
              takes a different approach: snap a photo of your W-2, and AI
              extracts your information and prepares your return in minutes.
              Both federal and state filing are{" "}
              <strong className="text-foreground">free — no income limits, no hidden fees, no upsells</strong>.
            </p>
            <p className="mt-3">
              FileFree is designed for first-time filers and anyone with a
              simple return who wants the fastest path from &ldquo;I have a
              W-2&rdquo; to &ldquo;my return is filed.&rdquo; Your SSN never
              leaves our encrypted server and is never sent to any AI service.
            </p>
          </section>

          {/* Comparison Table */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Quick Comparison
            </h2>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      Option
                    </th>
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      Federal
                    </th>
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      State
                    </th>
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      Income Limit
                    </th>
                    <th className="py-3 font-semibold text-foreground">
                      Format
                    </th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">IRS Free File</td>
                    <td className="py-3 pr-4 text-green-400">Free</td>
                    <td className="py-3 pr-4">Varies</td>
                    <td className="py-3 pr-4">$84,000 AGI</td>
                    <td className="py-3">Online</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">IRS Direct File</td>
                    <td className="py-3 pr-4 text-green-400">Free</td>
                    <td className="py-3 pr-4">Limited states</td>
                    <td className="py-3 pr-4">None</td>
                    <td className="py-3">Online</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">VITA</td>
                    <td className="py-3 pr-4 text-green-400">Free</td>
                    <td className="py-3 pr-4 text-green-400">Free</td>
                    <td className="py-3 pr-4">$67,000</td>
                    <td className="py-3">In-person</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">FreeTaxUSA</td>
                    <td className="py-3 pr-4 text-green-400">Free</td>
                    <td className="py-3 pr-4">$14.99</td>
                    <td className="py-3 pr-4">None</td>
                    <td className="py-3">Online</td>
                  </tr>
                  <tr>
                    <td className="py-3 pr-4 font-medium text-violet-400">
                      FileFree
                    </td>
                    <td className="py-3 pr-4 text-green-400">Free</td>
                    <td className="py-3 pr-4 text-green-400">Free</td>
                    <td className="py-3 pr-4">None</td>
                    <td className="py-3">Mobile/Web</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* Tips */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Tips for Filing for Free
            </h2>
            <ul className="mt-3 list-inside list-disc space-y-2">
              <li>
                <strong className="text-foreground">
                  Always start from IRS.gov.
                </strong>{" "}
                Some companies advertise &ldquo;free&rdquo; but upsell once you
                enter data. Starting from the official IRS Free File page
                ensures you get the genuinely free version.
              </li>
              <li>
                <strong className="text-foreground">
                  Gather documents first.
                </strong>{" "}
                Have your W-2, last year&apos;s AGI, and your SSN ready before
                starting. This avoids frustration mid-flow.
              </li>
              <li>
                <strong className="text-foreground">
                  File early, avoid the rush.
                </strong>{" "}
                Filing in February means faster refunds and less competition
                for VITA appointments.
              </li>
              <li>
                <strong className="text-foreground">
                  Choose direct deposit.
                </strong>{" "}
                You&apos;ll get your refund in about 21 days instead of 6-8
                weeks with a paper check.
              </li>
            </ul>
          </section>

          {/* FAQ */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Frequently Asked Questions
            </h2>
            <div className="mt-4 space-y-6">
              {faqItems.map((item) => (
                <div key={item.question}>
                  <h3 className="text-base font-semibold text-foreground">
                    {item.question}
                  </h3>
                  <p className="mt-1 text-base">{item.answer}</p>
                </div>
              ))}
            </div>
          </section>

          {/* CTA */}
          <section className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-8 text-center">
            <h2 className="text-2xl font-bold text-foreground">
              Ready to file for free?
            </h2>
            <p className="mt-2 text-base text-muted-foreground">
              Snap a photo of your W-2 and get your completed return in
              minutes. No income limits, no hidden fees.
            </p>
            <Link
              href="/demo"
              className="mt-6 inline-block rounded-lg bg-violet-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-violet-500"
            >
              Try the Demo &rarr;
            </Link>
          </section>
        </div>
      </article>
    </main>
  );
}
