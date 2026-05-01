import Link from "next/link";
import { AlertTriangle, BookOpen, Lock } from "lucide-react";

import type { DocHubEntry } from "@/lib/docs";
import type { FreshnessLevel } from "@/lib/doc-metadata";
import { HUB_CATEGORY_LABEL, monthsSinceReview } from "@/lib/doc-metadata";

function freshnessStyles(level: FreshnessLevel): string {
  switch (level) {
    case "fresh":
      return "bg-[var(--status-success-bg)] text-[var(--status-success)]";
    case "aging":
      return "bg-[var(--status-warning-bg)] text-[var(--status-warning)]";
    case "stale":
      return "bg-[var(--status-danger-bg)] text-[var(--status-danger)]";
    default:
      return "bg-zinc-800 text-[var(--status-muted)]";
  }
}

function freshnessLabel(level: FreshnessLevel): string {
  switch (level) {
    case "fresh":
      return "Fresh";
    case "aging":
      return "Aging";
    case "stale":
      return "Stale";
    default:
      return "Unknown";
  }
}

export function DocsHubDocCard({ doc }: { doc: DocHubEntry }) {
  const isImmutable = doc.category === "philosophy";
  return (
    <Link
      href={`/admin/docs/${doc.slug}`}
      data-testid="docs-hub-card"
      data-hub-category={doc.hubCategory}
      className="group flex flex-col rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 transition hover:border-zinc-700 hover:bg-zinc-900/70"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <span className="text-sm font-semibold text-zinc-100 group-hover:text-white">{doc.title}</span>
        {!doc.exists ? (
          <span
            title="File missing on disk — update docs/_index.yaml or restore the doc."
            className="flex shrink-0 items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[10px] font-medium text-rose-300"
          >
            <AlertTriangle className="h-3 w-3" />
            missing
          </span>
        ) : null}
      </div>

      {doc.freshness === "stale" && doc.lastReviewed ? (
        <p
          className="mt-2 rounded-md border px-2.5 py-1.5 text-[11px]"
          style={{
            backgroundColor: "var(--status-danger-bg)",
            color: "var(--status-danger)",
            borderColor: "color-mix(in srgb, var(--status-danger) 35%, transparent)",
          }}
        >
          Last reviewed {monthsSinceReview(doc.lastReviewed)} months ago
        </p>
      ) : null}

      <p className="mt-2 line-clamp-2 text-xs text-zinc-500">{doc.summary}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-300">
          {HUB_CATEGORY_LABEL[doc.hubCategory]}
        </span>
        {isImmutable ? (
          <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
            <Lock className="h-3 w-3" />
            immutable
          </span>
        ) : null}
        <span className="rounded-full bg-zinc-800/80 px-2 py-0.5 text-[10px] text-zinc-400">
          {doc.readMinutes > 0 ? `${doc.readMinutes} min read` : "—"}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${freshnessStyles(doc.freshness)}`}
        >
          {freshnessLabel(doc.freshness)}
        </span>
      </div>

      {doc.lastReviewed ? (
        <p className="mt-2 text-[10px] text-zinc-600">Last reviewed {doc.lastReviewed}</p>
      ) : (
        <p className="mt-2 text-[10px] text-zinc-600">Last reviewed —</p>
      )}

      <div className="mt-3 flex flex-wrap gap-1 border-t border-zinc-800/60 pt-3">
        <BookOpen className="mr-1 h-3.5 w-3.5 shrink-0 text-zinc-600" aria-hidden />
        {doc.owners.slice(0, 3).map((owner) => (
          <span
            key={owner}
            className="rounded-full bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-medium text-sky-300"
          >
            {owner}
          </span>
        ))}
      </div>
    </Link>
  );
}
