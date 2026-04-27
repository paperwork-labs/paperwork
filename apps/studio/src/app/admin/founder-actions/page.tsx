import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink, FileText } from "lucide-react";

import founderData from "@/data/founder-actions.json";

export const dynamic = "force-static";
export const revalidate = 300;

const DOC_BLOB =
  "https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/FOUNDER_ACTIONS.md";

type Item = (typeof founderData.tiers)[number]["items"][number];

function Md({ text }: { text: string }) {
  if (!text.trim()) {
    return null;
  }
  return (
    <div
      className="prose prose-invert prose-sm max-w-none text-zinc-300 prose-p:my-1 prose-a:text-sky-400 prose-a:underline-offset-2 hover:prose-a:text-sky-300 prose-code:rounded prose-code:bg-zinc-800/80 prose-code:px-1 prose-code:py-0.5 prose-code:text-zinc-200"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

function ActionCard({ item, tierId }: { item: Item; tierId: string }) {
  return (
    <div
      className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4 shadow-sm"
      data-tier={tierId}
    >
      <h3 className="text-sm font-semibold text-zinc-100">{item.title}</h3>
      {item.why ? (
        <div className="mt-2 space-y-0.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
            Why this matters
          </p>
          <Md text={item.why} />
        </div>
      ) : null}
      {item.where ? (
        <div className="mt-2 space-y-0.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
            Where
          </p>
          <Md text={item.where} />
        </div>
      ) : null}
      {item.steps.length > 0 ? (
        <div className="mt-2 space-y-1.5 pl-0.5 text-sm text-zinc-300">
          {item.steps.map((s) => (
            <Md key={s} text={s} />
          ))}
        </div>
      ) : null}
      {item.verification ? (
        <div className="mt-2 space-y-0.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
            Verification
          </p>
          <Md text={item.verification} />
        </div>
      ) : null}
      {item.eta ? (
        <p className="mt-2 text-xs text-zinc-500">ETA: {item.eta}</p>
      ) : null}
      {item.source ? (
        <p className="mt-1 text-xs text-zinc-600">Source: {item.source}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <a
          href={item.runbookUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500/15 px-3 py-1.5 text-xs font-medium text-amber-200 ring-1 ring-amber-500/30 transition hover:bg-amber-500/25"
        >
          Open runbook
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}

export default function FounderActionsPage() {
  const { tiers, resolved, generated, sourceFile, counts } = founderData;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <FileText className="h-5 w-5 text-amber-300" />
          <h1 className="text-xl font-semibold text-zinc-100">
            Founder actions
          </h1>
        </div>
        <p className="max-w-3xl text-sm text-zinc-400">
          One-time work that needs founder credentials: Vercel, Render,
          GitHub, DNS, and vendor dashboards. Canonical list lives in{" "}
          <code className="text-zinc-300">{sourceFile}</code> and syncs at
          build time.
        </p>
        <p className="text-xs text-zinc-500">
          Generated {generated}. Pending: {counts.totalPending} (critical:{" "}
          {counts.critical}, operational: {counts.operational}, branding:{" "}
          {counts.branding}).
        </p>
        <a
          href={DOC_BLOB}
          target="_blank"
          rel="noreferrer"
          className="inline-flex text-sm text-sky-400 hover:text-sky-300"
        >
          View on GitHub
        </a>
      </header>

      {tiers.map((tier) => (
        <section
          key={tier.id}
          className="space-y-3 rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5"
        >
          <h2 className="text-sm font-semibold tracking-wide text-zinc-200">
            {tier.label}
          </h2>
          <div className="space-y-4">
            {tier.items.map((item) => (
              <ActionCard key={item.title} item={item} tierId={tier.id} />
            ))}
          </div>
        </section>
      ))}

      <section className="space-y-3 rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5">
        <h2 className="text-sm font-semibold tracking-wide text-zinc-200">
          Resolved
        </h2>
        <ul className="list-disc space-y-2 pl-4 text-sm text-zinc-400">
          {resolved.length === 0 ? (
            <li className="list-none pl-0 text-zinc-500">None listed.</li>
          ) : (
            resolved.map((line) => (
              <li key={line} className="pl-0.5">
                {line}
              </li>
            ))
          )}
        </ul>
        <p className="text-xs text-zinc-500">
          To record completion, edit{" "}
          <Link
            href={DOC_BLOB}
            className="text-sky-500 hover:text-sky-400"
            target="_blank"
            rel="noreferrer"
          >
            docs/infra/FOUNDER_ACTIONS.md
          </Link>{" "}
          on a branch and move items to the Resolved section.
        </p>
      </section>
    </div>
  );
}
