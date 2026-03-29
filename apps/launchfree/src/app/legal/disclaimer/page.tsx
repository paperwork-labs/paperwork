import type { Metadata } from "next";
import Link from "next/link";

const LAST_UPDATED = "March 28, 2026";

export const metadata: Metadata = {
  title: "Disclaimer",
  description:
    "General disclaimers for LaunchFree: document preparation only, not legal or tax advice, and user responsibility for accuracy.",
  openGraph: {
    title: "Disclaimer — LaunchFree",
    description:
      "General disclaimers for LaunchFree: document preparation only, not legal or tax advice, and user responsibility for accuracy.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function DisclaimerPage() {
  return (
    <article className="prose prose-invert prose-slate max-w-none prose-headings:scroll-mt-24 prose-headings:font-bold prose-headings:tracking-tight prose-a:text-cyan-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-100">
      <p className="text-sm text-slate-400 not-prose">Last updated: {LAST_UPDATED}</p>
      <h1 className="not-prose bg-gradient-to-r from-teal-400 to-cyan-500 bg-clip-text text-3xl font-bold tracking-tight text-transparent sm:text-4xl">
        Disclaimer
      </h1>
      <p className="lead text-slate-300">
        This page summarizes important limitations of LaunchFree, a service operated by Paperwork Labs
        LLC. By using LaunchFree, you acknowledge the following.
      </p>

      <div className="not-prose rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-4 text-slate-200">
        <p className="m-0 text-sm font-semibold text-cyan-300">Unauthorized practice of law (UPL)</p>
        <p className="mt-2 mb-0 text-sm leading-relaxed">
          LaunchFree provides document preparation services only. We are not a law firm and do not
          provide legal advice. For legal advice, consult a licensed attorney.
        </p>
      </div>

      <h2>Not legal advice</h2>
      <p>
        Content on LaunchFree is for general informational purposes. It does not create an
        attorney-client relationship and is not a substitute for advice from a qualified lawyer about
        your specific facts, entity choice, operating agreements, contracts, disputes, or regulatory
        obligations.
      </p>

      <h2>Not tax or financial advice</h2>
      <p>
        We do not provide tax, accounting, investment, or financial planning advice. Entity and tax
        elections can have significant consequences. Consult a certified public accountant, enrolled
        agent, or other qualified professional before making tax or financial decisions.
      </p>

      <h2>Accuracy of your information</h2>
      <p>
        You are responsible for the accuracy and completeness of all information you provide. Errors or
        omissions may delay or jeopardize a filing. You should review all generated documents carefully
        before submission.
      </p>

      <h2>State filing outcomes and timing</h2>
      <p>
        State agencies control whether a filing is accepted, rejected, or requires correction.
        Processing times vary by state, workload, and channel (online, mail, or otherwise). We do not
        guarantee approval, filing dates, or turnaround times.
      </p>

      <h2>No warranty</h2>
      <p>
        The Service is provided as described in our{" "}
        <Link href="/legal/terms" className="text-cyan-400 hover:underline">
          Terms of Service
        </Link>
        , without warranties beyond those required by law. See the Terms for full disclaimers and
        limitations of liability.
      </p>

      <h2>Contact</h2>
      <p>
        Questions: <a href="mailto:hello@launchfree.ai">hello@launchfree.ai</a>
      </p>
      <p className="text-sm text-slate-400">
        <Link href="/legal/privacy" className="text-cyan-400 hover:underline">
          Privacy Policy
        </Link>
        {" · "}
        <Link href="/legal/terms" className="text-cyan-400 hover:underline">
          Terms of Service
        </Link>
      </p>
    </article>
  );
}
