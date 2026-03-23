import type { Metadata } from "next";
import Link from "next/link";

import { JsonLd } from "@/components/json-ld";

export const metadata: Metadata = {
  title: "2025 Standard Deduction Amounts (Tax Year 2025) — FileFree",
  description:
    "The 2025 standard deduction is $15,750 for single filers, $31,500 for married filing jointly, and $23,625 for head of household. Learn when to take the standard deduction vs. itemize.",
  keywords: [
    "standard deduction 2025",
    "standard deduction amount 2025",
    "2025 tax deduction",
    "standard vs itemized deduction",
  ],
};

const faqItems = [
  {
    question: "What is the standard deduction for 2025?",
    answer:
      "For tax year 2025, the standard deduction is $15,750 for single filers and married filing separately, $31,500 for married filing jointly and qualifying surviving spouse, and $23,625 for head of household.",
  },
  {
    question: "Should I take the standard deduction or itemize?",
    answer:
      "Take the standard deduction unless your itemized deductions (mortgage interest, state/local taxes up to $10,000, charitable donations, medical expenses above 7.5% of AGI) add up to more than your standard deduction amount. About 90% of taxpayers take the standard deduction.",
  },
  {
    question: "Do I get a bigger standard deduction if I'm over 65?",
    answer:
      "Yes. For tax year 2025, filers age 65 or older get an additional $2,000 if single or head of household, or an additional $1,600 per qualifying spouse if married filing jointly. Blind filers get the same additional amounts.",
  },
  {
    question: "Can I claim the standard deduction if I'm claimed as a dependent?",
    answer:
      "Yes, but your standard deduction is limited. For 2025, a dependent's standard deduction is the greater of $1,350 or their earned income plus $450, up to the normal standard deduction amount for their filing status.",
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

export default function StandardDeduction2025Page() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <JsonLd data={jsonLd} />

      <article className="mx-auto max-w-3xl px-4 py-16">
        <Link
          href="/"
          className="text-sm text-muted-foreground transition hover:text-foreground"
        >
          &larr; Back to FileFree
        </Link>

        <h1 className="mt-8 text-3xl font-bold tracking-tight md:text-4xl">
          2025 Standard Deduction Amounts
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          The standard deduction reduces your taxable income by a fixed amount
          based on your filing status. Here are the official amounts for tax
          year 2025, sourced from{" "}
          <span className="text-foreground">
            Rev. Proc. 2024-40 as amended by P.L. 119-21
          </span>
          .
        </p>

        <div className="mt-12 space-y-10 text-lg leading-relaxed text-muted-foreground">
          {/* Amounts Table */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              2025 Standard Deduction by Filing Status
            </h2>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      Filing Status
                    </th>
                    <th className="py-3 font-semibold text-foreground">
                      Standard Deduction
                    </th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">Single</td>
                    <td className="py-3 font-semibold text-foreground">
                      $15,750
                    </td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">
                      Married Filing Jointly (MFJ)
                    </td>
                    <td className="py-3 font-semibold text-foreground">
                      $31,500
                    </td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">
                      Married Filing Separately (MFS)
                    </td>
                    <td className="py-3 font-semibold text-foreground">
                      $15,750
                    </td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">Head of Household (HoH)</td>
                    <td className="py-3 font-semibold text-foreground">
                      $23,625
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 pr-4">
                      Qualifying Surviving Spouse
                    </td>
                    <td className="py-3 font-semibold text-foreground">
                      $31,500
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              Source: IRS Revenue Procedure 2024-40 as amended by Public Law
              119-21 (One Big Beautiful Bill Act).
            </p>
          </section>

          {/* What is the standard deduction */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              What Is the Standard Deduction?
            </h2>
            <p className="mt-3">
              The standard deduction is a fixed dollar amount the IRS lets you
              subtract from your adjusted gross income (AGI) before calculating
              the tax you owe. It exists so that most taxpayers don&apos;t need
              to track individual deductions — you just get a flat reduction.
            </p>
            <p className="mt-3">
              For example, if you&apos;re a single filer earning $50,000, you
              subtract the $15,750 standard deduction and only pay tax on
              $34,250.
            </p>
          </section>

          {/* Standard vs Itemized */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Standard Deduction vs. Itemized Deductions
            </h2>
            <p className="mt-3">
              You choose one or the other — you can&apos;t take both. The IRS
              gives you two options:
            </p>
            <ul className="mt-3 list-inside list-disc space-y-2">
              <li>
                <strong className="text-foreground">
                  Standard deduction:
                </strong>{" "}
                A flat amount based on your filing status. No receipts needed.
                About 90% of taxpayers choose this.
              </li>
              <li>
                <strong className="text-foreground">
                  Itemized deductions:
                </strong>{" "}
                You add up qualifying expenses (mortgage interest, SALT taxes,
                charitable gifts, medical costs) and deduct the total. Only
                worth it if the sum exceeds your standard deduction.
              </li>
            </ul>
          </section>

          {/* When to itemize */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              When Does Itemizing Make Sense?
            </h2>
            <p className="mt-3">Consider itemizing if you have:</p>
            <ul className="mt-3 list-inside list-disc space-y-2">
              <li>
                <strong className="text-foreground">
                  A mortgage:
                </strong>{" "}
                Mortgage interest on loans up to $750,000 is deductible
              </li>
              <li>
                <strong className="text-foreground">
                  High state/local taxes:
                </strong>{" "}
                You can deduct state and local income or sales tax plus property
                tax, up to a combined $10,000 (SALT cap)
              </li>
              <li>
                <strong className="text-foreground">
                  Large charitable donations:
                </strong>{" "}
                Cash donations up to 60% of AGI and property donations at fair
                market value
              </li>
              <li>
                <strong className="text-foreground">
                  Significant medical expenses:
                </strong>{" "}
                Medical and dental costs exceeding 7.5% of your AGI
              </li>
            </ul>
            <p className="mt-3">
              Add these up. If the total exceeds $15,750 (single) or $31,500
              (MFJ), itemizing saves you money.
            </p>
          </section>

          {/* Additional deduction for 65+ */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Additional Standard Deduction for Age 65+ and Blind Filers
            </h2>
            <p className="mt-3">
              Taxpayers who are 65 or older, or who are legally blind, get an
              additional standard deduction on top of the base amount:
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      Filing Status
                    </th>
                    <th className="py-3 font-semibold text-foreground">
                      Additional Amount (per qualifying condition)
                    </th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">Single or Head of Household</td>
                    <td className="py-3 font-semibold text-foreground">
                      $2,000
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 pr-4">Married (filing jointly or separately)</td>
                    <td className="py-3 font-semibold text-foreground">
                      $1,600
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3">
              If you qualify as both 65+ <em>and</em> blind, you get the
              additional amount twice. For married couples, each spouse who
              qualifies adds their own additional deduction.
            </p>
            <p className="mt-3">
              <strong className="text-foreground">Example:</strong> A single
              filer age 68 gets a standard deduction of $15,750 + $2,000 ={" "}
              <strong className="text-foreground">$17,750</strong>.
            </p>
          </section>

          {/* Dependents */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Standard Deduction for Dependents
            </h2>
            <p className="mt-3">
              If someone else can claim you as a dependent, your standard
              deduction is limited to the greater of:
            </p>
            <ul className="mt-3 list-inside list-disc space-y-2">
              <li>
                <strong className="text-foreground">$1,350</strong>, or
              </li>
              <li>
                Your earned income plus{" "}
                <strong className="text-foreground">$450</strong> (up to the
                regular standard deduction for your filing status)
              </li>
            </ul>
            <p className="mt-3">
              This mainly affects teenagers and college students with part-time
              jobs who are still claimed on their parents&apos; return.
            </p>
          </section>

          {/* Changes from 2024 */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              How Has the Standard Deduction Changed?
            </h2>
            <p className="mt-3">
              The standard deduction adjusts annually for inflation. Here&apos;s
              how 2025 compares to recent years:
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      Tax Year
                    </th>
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      Single
                    </th>
                    <th className="py-3 pr-4 font-semibold text-foreground">
                      MFJ
                    </th>
                    <th className="py-3 font-semibold text-foreground">HoH</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">2023</td>
                    <td className="py-3 pr-4">$13,850</td>
                    <td className="py-3 pr-4">$27,700</td>
                    <td className="py-3">$20,800</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-3 pr-4">2024</td>
                    <td className="py-3 pr-4">$14,600</td>
                    <td className="py-3 pr-4">$29,200</td>
                    <td className="py-3">$21,900</td>
                  </tr>
                  <tr>
                    <td className="py-3 pr-4 font-medium text-violet-400">
                      2025
                    </td>
                    <td className="py-3 pr-4 font-medium text-violet-400">
                      $15,750
                    </td>
                    <td className="py-3 pr-4 font-medium text-violet-400">
                      $31,500
                    </td>
                    <td className="py-3 font-medium text-violet-400">
                      $23,625
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              The 2025 amounts reflect an approximately 7.9% increase from 2024,
              due to inflation adjustments under Rev. Proc. 2024-40 as amended
              by P.L. 119-21.
            </p>
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
              FileFree applies the right deduction automatically
            </h2>
            <p className="mt-2 text-base text-muted-foreground">
              Upload your W-2, and FileFree determines your filing status and
              applies the correct standard deduction — no guesswork needed.
              Free forever.
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
