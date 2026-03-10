import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "What Is a W-2 Form? Everything You Need to Know — FileFree",
  description:
    "Learn what a W-2 form is, who gets one, what every box means, key deadlines, and what to do if yours is missing. A plain-English guide from FileFree.",
  keywords: [
    "what is a W-2 form",
    "W-2 explained",
    "W-2 boxes",
    "W-2 deadline",
    "understanding your W-2",
  ],
};

const faqItems = [
  {
    question: "When should I receive my W-2?",
    answer:
      "Your employer is required to send your W-2 by January 31. If you haven't received it by mid-February, contact your employer first. If that doesn't work, call the IRS at 1-800-829-1040.",
  },
  {
    question: "What is the difference between a W-2 and a 1099?",
    answer:
      "A W-2 is for employees — your employer withholds income tax, Social Security, and Medicare from your pay. A 1099 is for independent contractors and other non-employment income — no taxes are withheld, so you're responsible for paying estimated taxes.",
  },
  {
    question: "How many copies of the W-2 are there?",
    answer:
      "Your employer prepares multiple copies: Copy A goes to the Social Security Administration, Copy B is for your federal tax return, Copy C is for your records, Copy D stays with the employer, Copy 1 goes to state/local tax agencies, and Copy 2 is for your state return.",
  },
  {
    question: "Can I file my taxes without a W-2?",
    answer:
      "Yes, but it's not ideal. You can use your last pay stub to estimate your income and file Form 4852 (Substitute for Form W-2) with the IRS. You may need to amend your return later once the actual W-2 arrives.",
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

export default function WhatIsAW2Page() {
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
          What Is a W-2 Form? Everything You Need to Know
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          If you work for an employer, you&apos;ll get a W-2 every January.
          Here&apos;s what it is, what every box means, and how to use it to
          file your taxes.
        </p>

        <div className="mt-12 space-y-10 text-lg leading-relaxed text-muted-foreground">
          {/* What is a W-2 */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              What Is a W-2?
            </h2>
            <p className="mt-3">
              A W-2, officially called the{" "}
              <strong className="text-foreground">
                Wage and Tax Statement
              </strong>
              , is a tax form your employer sends you each year. It reports your
              total earnings and the amount of federal, state, and other taxes
              withheld from your paycheck during the previous year.
            </p>
            <p className="mt-3">
              You need your W-2 to file your tax return. Your employer also
              sends a copy to the IRS and the Social Security Administration, so
              the numbers on your return need to match.
            </p>
          </section>

          {/* Who gets one */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Who Gets a W-2?
            </h2>
            <p className="mt-3">
              You&apos;ll receive a W-2 if you were an{" "}
              <strong className="text-foreground">employee</strong> at any point
              during the year and earned at least $600, or had any amount of
              income tax, Social Security, or Medicare withheld. This applies to
              full-time, part-time, and seasonal employees.
            </p>
            <p className="mt-3">
              If you worked as an{" "}
              <strong className="text-foreground">
                independent contractor
              </strong>{" "}
              (freelancer, gig worker), you&apos;ll get a 1099 instead — not a
              W-2.
            </p>
          </section>

          {/* The Boxes */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              W-2 Boxes Explained
            </h2>
            <p className="mt-3">
              A W-2 has a lot of boxes. Here&apos;s what the important ones
              mean:
            </p>

            <div className="mt-4 space-y-4">
              <div className="rounded-lg border border-white/10 p-4">
                <h3 className="font-semibold text-foreground">
                  Boxes a–f: Identifying Information
                </h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-base">
                  <li>
                    <strong className="text-foreground">Box a:</strong> Your
                    Social Security Number
                  </li>
                  <li>
                    <strong className="text-foreground">Box b:</strong>{" "}
                    Employer&apos;s EIN (Employer Identification Number)
                  </li>
                  <li>
                    <strong className="text-foreground">Box c:</strong>{" "}
                    Employer&apos;s name and address
                  </li>
                  <li>
                    <strong className="text-foreground">Box d:</strong> Control
                    number (employer&apos;s internal tracking — you can usually
                    ignore this)
                  </li>
                  <li>
                    <strong className="text-foreground">Box e–f:</strong> Your
                    name and address
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-white/10 p-4">
                <h3 className="font-semibold text-foreground">
                  Boxes 1–2: Income &amp; Federal Tax
                </h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-base">
                  <li>
                    <strong className="text-foreground">Box 1:</strong> Wages,
                    tips, and other compensation — your total taxable income
                    from this employer
                  </li>
                  <li>
                    <strong className="text-foreground">Box 2:</strong> Federal
                    income tax withheld — the total federal tax taken from your
                    paychecks
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-white/10 p-4">
                <h3 className="font-semibold text-foreground">
                  Boxes 3–6: Social Security &amp; Medicare
                </h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-base">
                  <li>
                    <strong className="text-foreground">Box 3:</strong> Social
                    Security wages (may differ from Box 1 if you have pre-tax
                    deductions)
                  </li>
                  <li>
                    <strong className="text-foreground">Box 4:</strong> Social
                    Security tax withheld
                  </li>
                  <li>
                    <strong className="text-foreground">Box 5:</strong> Medicare
                    wages and tips
                  </li>
                  <li>
                    <strong className="text-foreground">Box 6:</strong> Medicare
                    tax withheld
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-white/10 p-4">
                <h3 className="font-semibold text-foreground">
                  Boxes 7–11: Tips, Benefits &amp; Deferred Compensation
                </h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-base">
                  <li>
                    <strong className="text-foreground">Box 7:</strong> Social
                    Security tips
                  </li>
                  <li>
                    <strong className="text-foreground">Box 8:</strong>{" "}
                    Allocated tips (tips your employer assigned to you — common
                    in food service)
                  </li>
                  <li>
                    <strong className="text-foreground">Box 10:</strong>{" "}
                    Dependent care benefits
                  </li>
                  <li>
                    <strong className="text-foreground">Box 11:</strong>{" "}
                    Nonqualified deferred compensation plans
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-white/10 p-4">
                <h3 className="font-semibold text-foreground">
                  Box 12: Coded Items (a–d)
                </h3>
                <p className="mt-2 text-base">
                  Box 12 uses letter codes for various benefits and deductions.
                  Common ones include:
                </p>
                <ul className="mt-2 list-inside list-disc space-y-1 text-base">
                  <li>
                    <strong className="text-foreground">Code D:</strong> 401(k)
                    contributions
                  </li>
                  <li>
                    <strong className="text-foreground">Code DD:</strong> Cost
                    of employer-sponsored health coverage (informational only —
                    not taxable)
                  </li>
                  <li>
                    <strong className="text-foreground">Code W:</strong> HSA
                    contributions
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-white/10 p-4">
                <h3 className="font-semibold text-foreground">
                  Boxes 13–14: Checkboxes &amp; Other Info
                </h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-base">
                  <li>
                    <strong className="text-foreground">Box 13:</strong>{" "}
                    Checkboxes for statutory employee, retirement plan
                    participant, and third-party sick pay
                  </li>
                  <li>
                    <strong className="text-foreground">Box 14:</strong> Other —
                    employers use this for additional info like union dues,
                    state disability insurance, or tuition assistance
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-white/10 p-4">
                <h3 className="font-semibold text-foreground">
                  Boxes 15–17: State &amp; Local Taxes
                </h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-base">
                  <li>
                    <strong className="text-foreground">Box 15:</strong>{" "}
                    State and employer&apos;s state ID number
                  </li>
                  <li>
                    <strong className="text-foreground">Box 16:</strong> State
                    wages, tips, etc.
                  </li>
                  <li>
                    <strong className="text-foreground">Box 17:</strong> State
                    income tax withheld
                  </li>
                </ul>
              </div>
            </div>
          </section>

          {/* Deadlines */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Key W-2 Deadlines
            </h2>
            <ul className="mt-3 list-inside list-disc space-y-2">
              <li>
                <strong className="text-foreground">January 31:</strong>{" "}
                Employers must send W-2s to employees and file them with the
                SSA
              </li>
              <li>
                <strong className="text-foreground">Mid-February:</strong> If
                you haven&apos;t received yours, contact your employer
              </li>
              <li>
                <strong className="text-foreground">April 15:</strong> Tax
                filing deadline for the 2025 tax year (unless extended)
              </li>
            </ul>
          </section>

          {/* Missing W-2 */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              What to Do If You Don&apos;t Get Your W-2
            </h2>
            <ol className="mt-3 list-inside list-decimal space-y-2">
              <li>
                <strong className="text-foreground">
                  Contact your employer.
                </strong>{" "}
                Ask HR or payroll for a copy. Confirm they have your correct
                address.
              </li>
              <li>
                <strong className="text-foreground">
                  Call the IRS.
                </strong>{" "}
                If your employer doesn&apos;t respond by mid-February, call
                1-800-829-1040. Have your employer&apos;s name, address, EIN,
                and your estimated wages ready.
              </li>
              <li>
                <strong className="text-foreground">
                  File with Form 4852.
                </strong>{" "}
                If the deadline is approaching and you still don&apos;t have
                your W-2, use Form 4852 (Substitute for Form W-2) with your
                best estimates from your last pay stub.
              </li>
              <li>
                <strong className="text-foreground">
                  Amend later if needed.
                </strong>{" "}
                If you filed with estimates and the W-2 arrives with different
                numbers, file Form 1040-X to amend.
              </li>
            </ol>
          </section>

          {/* FileFree mention */}
          <section>
            <h2 className="text-2xl font-bold text-foreground">
              Scanning Your W-2 with FileFree
            </h2>
            <p className="mt-3">
              Once you have your W-2, you don&apos;t need to manually type in
              every box.{" "}
              <Link
                href="/"
                className="text-violet-400 underline decoration-violet-400/30 hover:decoration-violet-400"
              >
                FileFree
              </Link>{" "}
              lets you snap a photo of your W-2, and AI reads every box
              automatically. You review the extracted data, confirm it&apos;s
              correct, and your return is ready in minutes.
            </p>
            <p className="mt-3">
              Your SSN is extracted securely on our server and is{" "}
              <strong className="text-foreground">
                never sent to any third-party AI service
              </strong>
              . All data is encrypted at rest.
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
              Got your W-2? File in minutes.
            </h2>
            <p className="mt-2 text-base text-muted-foreground">
              Take a photo, let AI do the data entry, and get your return
              done — for free.
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
