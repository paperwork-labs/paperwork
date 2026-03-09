import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service — FileFree",
  description:
    "Terms of service for FileFree, the free AI-powered tax filing app.",
};

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <article className="mx-auto max-w-2xl px-4 py-20">
        <Link
          href="/"
          className="text-sm text-muted-foreground transition hover:text-foreground"
        >
          &larr; Back to FileFree
        </Link>

        <h1 className="mt-8 text-3xl font-bold tracking-tight md:text-4xl">
          Terms of Service
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Last updated: March 9, 2026
        </p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-muted-foreground">
          <section>
            <h2 className="text-lg font-semibold text-foreground">
              What FileFree does
            </h2>
            <p className="mt-2">
              FileFree is a free tax preparation service that helps you create
              your federal and state tax returns. We use AI to read your W-2 and
              generate a completed return. You review it, and either download
              the PDF or e-file it.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Free means free
            </h2>
            <p className="mt-2">
              Tax filing through FileFree is free. Federal filing is free. State
              filing is free. There are no hidden fees, no upsells to a
              &quot;deluxe&quot; tier, and no surprises at checkout. We make
              money through optional financial product recommendations, not by
              charging you to file.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Your responsibilities
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>
                <strong>Accuracy:</strong> You are responsible for reviewing and
                confirming all information in your tax return before filing.
                FileFree extracts data using AI, but you must verify it is
                correct.
              </li>
              <li>
                <strong>Truthfulness:</strong> You agree to provide accurate and
                truthful information.
              </li>
              <li>
                <strong>Eligibility:</strong> You must be legally authorized to
                file a US tax return.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              AI-assisted preparation
            </h2>
            <p className="mt-2">
              FileFree uses artificial intelligence to extract information from
              your tax documents and prepare your return. While we strive for
              accuracy, AI can make errors. You should review all extracted data
              and calculated amounts before filing.
            </p>
            <p className="mt-2 rounded-lg border border-border/50 bg-card/30 p-4 text-xs">
              FileFree provides tax information for educational purposes. This
              is not professional tax advice. Consult a qualified tax
              professional for advice specific to your situation.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">E-filing</h2>
            <p className="mt-2">
              During our initial launch period, you can download your completed
              tax return as a PDF for free. E-file submission is provided
              through our e-file partner. FileFree is completing its own IRS
              e-file certification (target: January 2027), after which e-file
              will be available directly through FileFree at no cost.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Financial product recommendations
            </h2>
            <p className="mt-2">
              FileFree may display personalized financial product
              recommendations (such as high-yield savings accounts or IRA
              offers) based on your tax situation. These are optional. FileFree
              may receive compensation if you sign up for a recommended product.
              All recommendations are clearly labeled as such.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Account and data
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>
                You can delete your account at any time. Deletion removes all
                your data from our systems.
              </li>
              <li>
                We handle your data as described in our{" "}
                <Link
                  href="/privacy"
                  className="text-violet-500 hover:underline"
                >
                  Privacy Policy
                </Link>
                .
              </li>
              <li>
                We may suspend accounts that violate these terms or engage in
                fraudulent activity.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Limitation of liability
            </h2>
            <p className="mt-2">
              FileFree provides the service &quot;as is.&quot; To the maximum
              extent permitted by law, FileFree is not liable for indirect,
              incidental, special, consequential, or punitive damages, including
              lost profits, tax penalties, or interest resulting from errors in
              your tax return. Our total liability is limited to the amount you
              paid for the service (which is $0 for free filing).
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Dispute resolution
            </h2>
            <p className="mt-2">
              Any disputes will be resolved through binding arbitration under
              the rules of the American Arbitration Association, except that
              either party may bring claims in small claims court. You agree to
              resolve disputes individually, not as part of a class action.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Changes to these terms
            </h2>
            <p className="mt-2">
              We may update these terms. Material changes will be communicated
              via email or in-app notice at least 30 days before they take
              effect. Continued use after changes take effect constitutes
              acceptance.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Governing law
            </h2>
            <p className="mt-2">
              These terms are governed by the laws of the State of California,
              without regard to conflict of law provisions.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">Contact</h2>
            <p className="mt-2">
              Questions?{" "}
              <a
                href="mailto:legal@filefree.tax"
                className="text-violet-500 hover:underline"
              >
                legal@filefree.tax
              </a>
            </p>
          </section>
        </div>
      </article>
    </main>
  );
}
