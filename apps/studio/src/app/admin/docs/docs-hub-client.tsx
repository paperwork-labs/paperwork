"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertTriangle, BookOpen, Lock, Route } from "lucide-react";

import { DocsHubSearchForm } from "./docs-hub-search";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import type { DocHubEntry } from "@/lib/docs";
import type { FreshnessLevel, HubDocCategory } from "@/lib/doc-metadata";
import { HUB_CATEGORY_LABEL, monthsSinceReview } from "@/lib/doc-metadata";

export type ReadingPathClient = {
  id: string;
  title: string;
  est_minutes: number;
  /** Steps listed on the path (may exceed resolved slugs when aliases are missing). */
  docCount: number;
  resolvedCount: number;
  firstSlug: string | null;
};

const FILTER_ORDER: Array<{ id: HubDocCategory | "all"; label: string }> = [
  { id: "all", label: "All" },
  { id: "philosophy", label: "Philosophy" },
  { id: "architecture", label: "Architecture" },
  { id: "strategy", label: "Strategy" },
  { id: "runbook", label: "Runbook" },
  { id: "playbook", label: "Playbook" },
  { id: "decision-log", label: "Decision Log" },
];

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

export type DocsHubClientProps = {
  entries: DocHubEntry[];
  readingPaths: ReadingPathClient[];
};

export function DocsHubClient({ entries, readingPaths }: DocsHubClientProps) {
  const [activeFilter, setActiveFilter] = useState<HubDocCategory | "all">("all");

  const filtered = useMemo(() => {
    if (activeFilter === "all") return entries;
    return entries.filter((e) => e.hubCategory === activeFilter);
  }, [entries, activeFilter]);

  return (
    <div className="space-y-8">
      <HqPageHeader
        eyebrow="Knowledge"
        title="Docs"
        subtitle="One place for every persona to find philosophy, architecture, runbooks, and specs. Philosophy docs are CODEOWNERS-locked — they do not change without explicit sign-off. Anything under /admin/docs/{slug} is readable by agents for grounded responses."
        actions={
          <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
            agent-readable
          </span>
        }
      />

      <DocsHubSearchForm />

      <section aria-labelledby="reading-paths-heading" className="space-y-3">
        <div className="flex items-center gap-2">
          <Route className="h-4 w-4 text-sky-400" />
          <h2 id="reading-paths-heading" className="text-sm font-semibold text-zinc-200">
            Reading paths
          </h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {readingPaths.map((p) => {
            const href = p.firstSlug ? `/admin/docs/${p.firstSlug}` : "#reading-paths";
            return (
              <Link
                key={p.id}
                href={href}
                className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4 transition hover:border-sky-500/40 hover:bg-zinc-900"
              >
                <p className="text-sm font-medium text-zinc-100">{p.title}</p>
                <p className="mt-2 text-xs text-zinc-500">
                  {p.docCount} docs · ~{p.est_minutes} min
                </p>
              </Link>
            );
          })}
        </div>
      </section>

      <div className="space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
          Filter by category
        </p>
        <div
          className="flex flex-wrap gap-2"
          role="group"
          aria-label="Doc category filters"
        >
          {FILTER_ORDER.map((f) => {
            const pressed = activeFilter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                data-testid={f.id === "all" ? "docs-hub-filter-all" : `docs-hub-filter-${f.id}`}
                aria-pressed={pressed}
                onClick={() => setActiveFilter(f.id)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  pressed
                    ? "bg-sky-500/20 text-sky-200 ring-1 ring-sky-500/40"
                    : "bg-zinc-800/80 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                }`}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((doc) => {
          const isImmutable = doc.category === "philosophy";
          return (
            <article
              key={doc.slug}
              data-testid="docs-hub-card"
              data-hub-category={doc.hubCategory}
              className="flex flex-col rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 transition hover:border-zinc-700 hover:bg-zinc-900/70"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <Link
                  href={`/admin/docs/${doc.slug}`}
                  className="text-sm font-semibold text-zinc-100 hover:text-white"
                >
                  {doc.title}
                </Link>
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
                <p className="mt-2 text-[10px] text-zinc-600">
                  Last reviewed {doc.lastReviewed}
                </p>
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
            </article>
          );
        })}
      </div>
    </div>
  );
}
