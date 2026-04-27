import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink, FileText } from "lucide-react";

import founderData from "@/data/founder-actions.json";
import {
  extractVerificationUrls,
  probeAllUrls,
  type ProbeResult,
} from "@/lib/founder-action-probes";

export const revalidate = 120;

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

function LiveCheckPill({
  primaryUrl,
  result,
}: {
  primaryUrl: string | null;
  result: ProbeResult | undefined;
}) {
  if (!primaryUrl) return null;
  if (!result) {
    return (
      <span className="inline-flex items-center rounded-md border border-zinc-700/60 bg-zinc-800/40 px-2 py-0.5 text-[10px] text-zinc-500">
        Live check skipped
      </span>
    );
  }
  if (result.ok) {
    return (
      <span
        className="inline-flex items-center rounded-md border border-emerald-900/50 bg-emerald-950/30 px-2 py-0.5 text-[10px] text-emerald-200/90"
        title={`${result.status} ${result.url}`}
      >
        Live: reachable ({result.status})
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center rounded-md border border-zinc-700/80 bg-zinc-900/50 px-2 py-0.5 text-[10px] text-zinc-400"
      title={
        result.error
          ? `${result.error} — ${result.url}`
          : `${result.status || "no response"} — ${result.url}`
      }
    >
      Live: not reachable
      {result.status ? ` (${result.status})` : ""}
    </span>
  );
}

function ActionCard({
  item,
  tierId,
  probeByUrl,
}: {
  item: Item;
  tierId: string;
  probeByUrl: Map<string, ProbeResult>;
}) {
  const urls = extractVerificationUrls(item.verification ?? "");
  const primaryUrl = urls[0] ?? null;
  const result = primaryUrl ? probeByUrl.get(primaryUrl) : undefined;

  return (
    <div
      className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4 shadow-sm"
      data-tier={tierId}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-100">{item.title}</h3>
        <LiveCheckPill primaryUrl={primaryUrl} result={result} />
      </div>
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
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-600/60 bg-zinc-800/50 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-zinc-800"
        >
          Open runbook
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}

export default async function FounderActionsPage() {
  const { tiers, resolved, generated, sourceFile, counts } = founderData;

  const allUrls: string[] = [];
  for (const tier of tiers) {
    for (const item of tier.items) {
      allUrls.push(...extractVerificationUrls(item.verification ?? ""));
    }
  }
  const probeByUrl = await probeAllUrls(allUrls);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <FileText className="h-5 w-5 text-zinc-400" />
          <h1 className="text-xl font-semibold text-zinc-100">
            Founder actions
          </h1>
        </div>
        <p className="max-w-3xl text-sm text-zinc-400">
          One-time work that needs founder credentials: Vercel, Render,
          GitHub, DNS, and vendor dashboards. Canonical list lives in{" "}
          <code className="text-zinc-300">{sourceFile}</code> and syncs at
          build time.{" "}
          <strong className="font-medium text-zinc-300">
            Live checks
          </strong>{" "}
          re-run every ~2 minutes and hit the first HTTPS URL in each item&apos;s
          verification line — use them to spot stale markdown (doc says pending
          but endpoint is already up, or the opposite).
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
              <ActionCard
                key={item.title}
                item={item}
                tierId={tier.id}
                probeByUrl={probeByUrl}
              />
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
