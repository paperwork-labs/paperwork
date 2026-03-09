import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy — FileFree",
  description:
    "How FileFree handles your data. Plain English, no legalese.",
};

export default function PrivacyPage() {
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
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Last updated: March 9, 2026
        </p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-muted-foreground">
          <section>
            <h2 className="text-lg font-semibold text-foreground">
              The short version
            </h2>
            <p className="mt-2">
              We collect only what we need to prepare your tax return. We never
              sell your data. Your Social Security Number never leaves your
              device except to reach our encrypted database &mdash; it is never
              sent to any third-party AI service. You can delete your account and
              all associated data at any time.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              What we collect
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>
                <strong>Account information:</strong> Email address, name, and
                authentication provider (Google, Apple, or email/password).
              </li>
              <li>
                <strong>Tax documents:</strong> W-2 images you upload. These are
                stored in encrypted cloud storage and{" "}
                <strong>automatically deleted after 24 hours</strong>.
              </li>
              <li>
                <strong>Tax data:</strong> Information extracted from your
                documents (wages, withholdings, employer info). Encrypted at rest
                using AES-256 encryption.
              </li>
              <li>
                <strong>Social Security Number:</strong> Extracted locally on our
                server via pattern matching.{" "}
                <strong>
                  Never transmitted to any third-party AI service.
                </strong>{" "}
                Encrypted at rest with a separate encryption key.
              </li>
              <li>
                <strong>Usage data:</strong> Page views, feature usage, and
                error reports. All analytics are PII-scrubbed before
                transmission &mdash; no email addresses, SSNs, or financial data
                appear in analytics.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              How we use AI
            </h2>
            <p className="mt-2">
              Your tax documents are processed using AI technology to extract
              information accurately. Here&apos;s exactly how:
            </p>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>
                <strong>Google Cloud Vision:</strong> Reads text from your W-2
                image. Google does not store your images or use them for model
                training.
              </li>
              <li>
                <strong>OpenAI (GPT):</strong> Maps the extracted text to the
                correct W-2 fields. Your SSN is replaced with a placeholder
                (XXX-XX-XXXX) before any text is sent to OpenAI. OpenAI does not
                use API data for model training.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              How we protect your data
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>All data encrypted in transit (TLS) and at rest (AES-256)</li>
              <li>SSN stored with separate application-level encryption key</li>
              <li>
                W-2 images auto-deleted after 24 hours via cloud storage
                lifecycle policy
              </li>
              <li>
                PII-scrubbing middleware prevents sensitive data from appearing
                in logs
              </li>
              <li>
                Rate limiting and CSRF protection on all API endpoints
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              We never sell your data
            </h2>
            <p className="mt-2">
              We do not sell, rent, or trade your personal information. Period.
              Our revenue comes from optional financial product recommendations
              (clearly disclosed) and premium advisory features &mdash; never
              from selling your data.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Financial product referrals
            </h2>
            <p className="mt-2">
              FileFree may recommend financial products (such as high-yield
              savings accounts) based on your tax situation. If you sign up for
              a recommended product, FileFree may receive compensation from the
              provider. All recommendations are clearly labeled, and you are
              never required to use them.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Your rights
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>
                <strong>Access:</strong> Request a copy of all data we store
                about you.
              </li>
              <li>
                <strong>Delete:</strong> Delete your account and all associated
                data at any time. Deletion cascades across our database, cloud
                storage, and session store.
              </li>
              <li>
                <strong>Portability:</strong> Download your tax data in a
                standard format.
              </li>
              <li>
                <strong>Opt-out:</strong> We don&apos;t sell data, but you can
                opt out of analytics tracking at any time.
              </li>
            </ul>
            <p className="mt-2">
              These rights apply under CCPA (California), GDPR (EU), and similar
              privacy laws. To exercise any right, email{" "}
              <a
                href="mailto:privacy@filefree.tax"
                className="text-violet-500 hover:underline"
              >
                privacy@filefree.tax
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Third-party services
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>
                <strong>Google Cloud Vision:</strong> OCR processing (no image
                storage)
              </li>
              <li>
                <strong>OpenAI:</strong> Field mapping (no SSN, no model
                training)
              </li>
              <li>
                <strong>Neon (PostgreSQL):</strong> Database (encrypted at rest)
              </li>
              <li>
                <strong>Vercel:</strong> Frontend hosting
              </li>
              <li>
                <strong>Render:</strong> Backend hosting
              </li>
              <li>
                <strong>PostHog:</strong> Product analytics (PII-scrubbed)
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">
              Children&apos;s privacy
            </h2>
            <p className="mt-2">
              FileFree is not intended for users under 16. We do not knowingly
              collect data from children.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">Changes</h2>
            <p className="mt-2">
              We&apos;ll notify you of material changes via email or an in-app
              notice before they take effect.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-foreground">Contact</h2>
            <p className="mt-2">
              Questions?{" "}
              <a
                href="mailto:privacy@filefree.tax"
                className="text-violet-500 hover:underline"
              >
                privacy@filefree.tax
              </a>
            </p>
          </section>
        </div>
      </article>
    </main>
  );
}
