import type { Metadata } from "next";
import Link from "next/link";

const LAST_UPDATED = "March 28, 2026";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "Terms governing your use of LaunchFree LLC formation document preparation and filing services.",
  openGraph: {
    title: "Terms of Service — LaunchFree",
    description:
      "Terms governing your use of LaunchFree LLC formation document preparation and filing services.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function TermsOfServicePage() {
  return (
    <article className="prose prose-invert prose-slate max-w-none prose-headings:scroll-mt-24 prose-headings:font-bold prose-headings:tracking-tight prose-a:text-cyan-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-100">
      <p className="text-sm text-slate-400 not-prose">Last updated: {LAST_UPDATED}</p>
      <h1 className="not-prose bg-gradient-to-r from-teal-400 to-cyan-500 bg-clip-text text-3xl font-bold tracking-tight text-transparent sm:text-4xl">
        Terms of Service
      </h1>
      <p className="lead text-slate-300">
        These Terms of Service (&quot;Terms&quot;) govern your access to and use of LaunchFree, operated
        by Paperwork Labs LLC (&quot;Paperwork Labs,&quot; &quot;we,&quot; &quot;us,&quot; or
        &quot;our&quot;), including the website at launchfree.ai and related services (collectively, the
        &quot;Service&quot;). By using the Service, you agree to these Terms.
      </p>

      <div className="not-prose rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-4 text-slate-200">
        <p className="m-0 text-sm font-semibold text-cyan-300">Important — not legal advice</p>
        <p className="mt-2 mb-0 text-sm leading-relaxed">
          LaunchFree provides document preparation services only. We are not a law firm and do not
          provide legal advice. Communications with us do not create an attorney-client relationship.
          For legal advice, consult a licensed attorney in your jurisdiction.
        </p>
      </div>

      <h2>Service description</h2>
      <p>
        LaunchFree helps you prepare information and documents for forming a limited liability company
        and, where available, facilitates submission to the appropriate state filing office. Features
        may vary by state. We may use technology, templates, and third-party tools to generate documents
        and route filings. The Service does not guarantee that any state will approve your filing or
        that a particular business structure is suitable for you.
      </p>

      <h2>No legal, tax, or financial advice</h2>
      <p>
        Nothing on the Service is legal, tax, or financial advice. We do not analyze your specific
        situation or advise you on compliance, liability, taxation, securities, licensing, or
        employment law. You are solely responsible for consulting qualified professionals as needed.
      </p>

      <h2>Eligibility and account</h2>
      <p>
        You must be at least 18 years old and able to form a binding contract to use the Service. You
        agree to provide accurate, current, and complete information and to update it as needed. You are
        responsible for safeguarding your account credentials and for activity under your account.
      </p>

      <h2>User responsibilities</h2>
      <p>You agree that you will:</p>
      <ul>
        <li>Provide truthful, accurate information in connection with your formation;</li>
        <li>Comply with all applicable laws and state filing rules;</li>
        <li>Not use the Service for unlawful, fraudulent, or misleading purposes;</li>
        <li>Not attempt to interfere with or disrupt the Service or other users; and</li>
        <li>Review generated documents carefully before authorizing submission to a state agency.</li>
      </ul>

      <h2>Fees, state charges, and refunds</h2>
      <p>
        LaunchFree may offer document preparation without charging you a service fee; state filing
        offices charge their own fees, which you are responsible for paying when required.
        <strong> State filing fees and government charges are generally non-refundable</strong> once paid
        to the state or its designated processor, even if your filing is rejected, delayed, or
        withdrawn. Refund eligibility for any optional paid features will be described at the point of
        purchase.
      </p>

      <h2>Third parties</h2>
      <p>
        The Service may link to or integrate with third-party websites, payment processors, or state
        systems. We are not responsible for third-party content, policies, or failures outside our
        reasonable control.
      </p>

      <h2>Intellectual property</h2>
      <p>
        The Service, including software, branding, and materials we provide, is owned by Paperwork Labs
        or its licensors and is protected by intellectual property laws. We grant you a limited,
        non-exclusive, non-transferable license to use the Service for personal or internal business use
        in connection with LLC formation. You may not copy, reverse engineer, or resell the Service
        except as permitted by law.
      </p>

      <h2>Disclaimer of warranties</h2>
      <p>
        THE SERVICE IS PROVIDED &quot;AS IS&quot; AND &quot;AS AVAILABLE,&quot; WITHOUT WARRANTIES OF
        ANY KIND, WHETHER EXPRESS OR IMPLIED, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS
        FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE
        UNINTERRUPTED, ERROR-FREE, OR THAT DEFECTS WILL BE CORRECTED.
      </p>

      <h2>Limitation of liability</h2>
      <p>
        TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, PAPERWORK LABS AND ITS AFFILIATES, OFFICERS,
        DIRECTORS, EMPLOYEES, AND AGENTS WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL,
        CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, DATA, OR GOODWILL, ARISING FROM OR
        RELATED TO YOUR USE OF THE SERVICE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
      </p>
      <p>
        OUR TOTAL LIABILITY FOR ANY CLAIM ARISING OUT OF OR RELATING TO THE SERVICE OR THESE TERMS WILL
        NOT EXCEED THE GREATER OF (A) THE AMOUNTS YOU PAID TO US FOR THE SERVICE IN THE TWELVE (12)
        MONTHS BEFORE THE CLAIM OR (B) ONE HUNDRED U.S. DOLLARS (US $100), EXCEPT WHERE PROHIBITED BY
        LAW. SOME JURISDICTIONS DO NOT ALLOW CERTAIN LIMITATIONS; IN THOSE CASES, OUR LIABILITY IS
        LIMITED TO THE FULLEST EXTENT PERMITTED.
      </p>

      <h2>Indemnity</h2>
      <p>
        You will defend, indemnify, and hold harmless Paperwork Labs and its affiliates from any claims,
        damages, losses, and expenses (including reasonable attorneys&apos; fees) arising from your use
        of the Service, your content, or your violation of these Terms or applicable law.
      </p>

      <h2>Governing law and venue</h2>
      <p>
        These Terms are governed by the laws of the State of California, without regard to
        conflict-of-law principles. You agree that exclusive jurisdiction for disputes relating to these Terms or
        the Service lies in the state and federal courts located in California, except where prohibited
        by law.
      </p>

      <h2>Changes to these Terms</h2>
      <p>
        We may modify these Terms at any time. We will post the updated Terms on this page and update
        the &quot;Last updated&quot; date. If changes are material, we may provide additional notice
        (for example, by email or in-product message). Your continued use after the effective date
        constitutes acceptance of the revised Terms.
      </p>

      <h2>Termination</h2>
      <p>
        We may suspend or terminate your access to the Service at any time, with or without notice, for
        conduct that we believe violates these Terms or harms the Service or others. Provisions that by
        their nature should survive will survive termination.
      </p>

      <h2>Contact</h2>
      <p>
        For questions about these Terms:{" "}
        <a href="mailto:hello@launchfree.ai">hello@launchfree.ai</a>
      </p>
      <p className="text-sm text-slate-400">
        <Link href="/legal/privacy" className="text-cyan-400 hover:underline">
          Privacy Policy
        </Link>
        {" · "}
        <Link href="/legal/disclaimer" className="text-cyan-400 hover:underline">
          Disclaimer
        </Link>
      </p>
    </article>
  );
}
