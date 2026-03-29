import type { Metadata } from "next";
import Link from "next/link";

const LAST_UPDATED = "March 28, 2026";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How LaunchFree collects, uses, and protects your information when you use our free LLC formation service.",
  openGraph: {
    title: "Privacy Policy — LaunchFree",
    description:
      "How LaunchFree collects, uses, and protects your information when you use our free LLC formation service.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function PrivacyPolicyPage() {
  return (
    <article className="prose prose-invert prose-slate max-w-none prose-headings:scroll-mt-24 prose-headings:font-bold prose-headings:tracking-tight prose-a:text-cyan-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-slate-100">
      <p className="text-sm text-slate-400 not-prose">Last updated: {LAST_UPDATED}</p>
      <h1 className="not-prose bg-gradient-to-r from-teal-400 to-cyan-500 bg-clip-text text-3xl font-bold tracking-tight text-transparent sm:text-4xl">
        Privacy Policy
      </h1>
      <p className="lead text-slate-300">
        LaunchFree is operated by Paperwork Labs LLC (&quot;we,&quot; &quot;us,&quot; or &quot;our&quot;). This
        Privacy Policy describes how we collect, use, disclose, and safeguard information when you use
        LaunchFree at launchfree.ai (the &quot;Service&quot;).
      </p>

      <h2>Information we collect</h2>
      <p>We collect information you provide directly to us, including:</p>
      <ul>
        <li>
          <strong>Formation and business information</strong>, such as your proposed LLC name, state of
          formation, business address, registered agent details, and member or manager information you
          submit to prepare formation documents.
        </li>
        <li>
          <strong>Contact information</strong>, such as your name, email address, and phone number, when
          you provide them to create an account, receive updates, or communicate with us about your
          filing.
        </li>
        <li>
          <strong>Payment-related information</strong> when you pay state filing fees or related charges
          through our payment partners. Card data is processed by our payment service providers; we do
          not store full payment card numbers on our servers.
        </li>
        <li>
          <strong>Technical and usage data</strong>, such as device type, browser, IP address, and
          general usage information, to operate and secure the Service.
        </li>
      </ul>
      <p>
        <strong>LaunchFree is designed for business formation.</strong> We do not ask you for Social
        Security numbers for the core LLC formation flow. If you voluntarily provide sensitive
        information in a message to us, we will use it only as needed to respond and as described in this
        policy.
      </p>

      <h2>How we use information</h2>
      <p>We use the information we collect to:</p>
      <ul>
        <li>Prepare, review, and submit LLC formation documents on your behalf where you request it;</li>
        <li>Communicate with you about your formation, status updates, and support requests;</li>
        <li>Operate, maintain, and improve the Service, including security and fraud prevention;</li>
        <li>Comply with legal obligations and enforce our terms; and</li>
        <li>Analyze aggregated or de-identified usage to improve the product.</li>
      </ul>

      <h2>How we share information</h2>
      <p>We may share information in these situations:</p>
      <ul>
        <li>
          <strong>State filing agencies</strong>. When you ask us to file your LLC, we transmit the
          formation documents and information required by the applicable secretary of state or similar
          agency. Those agencies process filings under their own privacy notices and laws.
        </li>
        <li>
          <strong>Service providers</strong> who assist us (for example, hosting, email delivery,
          analytics, payment processing, or document generation), subject to contractual obligations to
          protect your information and use it only for the services they provide to us.
        </li>
        <li>
          <strong>Legal and safety</strong> when we believe disclosure is required by law, regulation,
          legal process, or to protect the rights, property, or safety of our users, Paperwork Labs, or
          others.
        </li>
        <li>
          <strong>Business transfers</strong> in connection with a merger, acquisition, or sale of assets,
          where your information may transfer as part of that transaction, consistent with applicable
          law.
        </li>
      </ul>
      <p>
        <strong>We do not sell your personal information</strong> and we do not share it for
        cross-context behavioral advertising as a &quot;sale&quot; under the California Consumer Privacy
        Act.
      </p>

      <h2>Data retention</h2>
      <p>
        We retain information for as long as necessary to provide the Service, comply with legal,
        accounting, and tax obligations, resolve disputes, and enforce our agreements. Formation records
        and related communications may be kept for periods required by law or reasonably necessary for
        our legitimate business purposes, including document integrity and regulatory compliance.
      </p>

      <h2>Security</h2>
      <p>
        We use administrative, technical, and organizational measures designed to protect your
        information, including encryption in transit (such as HTTPS) and access controls. No method of
        transmission or storage is completely secure; we encourage you to use strong passwords and
        protect your account credentials.
      </p>

      <h2>Your rights and choices</h2>
      <p>
        Depending on where you live, you may have rights to access, correct, delete, or port certain
        personal information, or to object to or restrict certain processing. California residents may
        have additional rights under the CCPA/CPRA. Individuals in the European Economic Area, UK, or
        Switzerland may have rights under the GDPR.
      </p>
      <p>
        To exercise applicable rights, contact us at{" "}
        <a href="mailto:hello@launchfree.ai">hello@launchfree.ai</a>. We will respond consistent with
        applicable law. You may also have the right to lodge a complaint with a data protection
        authority.
      </p>

      <h2>Children</h2>
      <p>
        The Service is not directed to children under 16, and we do not knowingly collect personal
        information from children.
      </p>

      <h2>Changes to this policy</h2>
      <p>
        We may update this Privacy Policy from time to time. We will post the updated version on this
        page and update the &quot;Last updated&quot; date. Material changes may be communicated through
        the Service or by email where appropriate.
      </p>

      <h2>Contact us</h2>
      <p>
        Questions about this Privacy Policy:{" "}
        <a href="mailto:hello@launchfree.ai">hello@launchfree.ai</a>
      </p>
      <p className="text-sm text-slate-400">
        Paperwork Labs LLC — California, United States.{" "}
        <Link href="/legal/terms" className="text-cyan-400 hover:underline">
          Terms of Service
        </Link>
        {" · "}
        <Link href="/legal/disclaimer" className="text-cyan-400 hover:underline">
          Disclaimer
        </Link>
      </p>
    </article>
  );
}
