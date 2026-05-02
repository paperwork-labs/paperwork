"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, BookOpen, Lock, Route } from "lucide-react";

import { DocsHubPersonaView } from "./docs-hub-persona-view";
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

function ReadingPathCard(p: ReadingPathClient) {
  const availability = `${p.resolvedCount} of ${p.docCount} docs available`;
  const partial = p.resolvedCount > 0 && p.resolvedCount < p.docCount;
  const empty = p.resolvedCount === 0;

  const meta = (
    <>
      <p className="mt-2 text-xs text-zinc-500">{availability}</p>
      <p className="mt-0.5 text-xs text-zinc-500">~{p.est_minutes} min</p>
      {partial ? (
        <p className="mt-2 flex items-center gap-1.5 text-[11px] font-medium text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Some steps are not in the docs index yet
        </p>
      ) : null}
    </>
  );

  if (empty || !p.firstSlug) {
    return (
      <div
        data-testid={`reading-path-${p.id}`}
        className="rounded-xl border border-zinc-800/60 bg-zinc-950/40 p-4 opacity-60"
        aria-label={`${p.title}, coming soon`}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className="text-sm font-medium text-zinc-400">{p.title}</p>
          <span className="shrink-0 rounded-full bg-zinc-800/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
            Coming soon
          </span>
        </div>
        {meta}
      </div>
    );
  }

  const href = `/admin/docs/${p.firstSlug}`;
  return (
    <Link
      href={href}
      data-testid={`reading-path-${p.id}`}
      className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4 transition hover:border-sky-500/40 hover:bg-zinc-900"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-sm font-medium text-zinc-100">{p.title}</p>
        {partial ? (
          <span className="text-amber-400" title="Not every listed doc resolves in the index">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
            <span className="sr-only">Partial path: some listed docs are missing from the index</span>
          </span>
        ) : null}
      </div>
      {meta}
    </Link>
  );
}

const FILTER_ORDER: Array<{ id: HubDocCategory | "all"; label: string }> = [
  { id: "all", label: "All" },
  { id: "philosophy", label: "Philosophy" },
  { id: "architecture", label: "Architecture" },
  { id: "strategy", label: "Strategy" },
  { id: "runbook", label: "Runbook" },
  { id: "playbook", label: "Playbook" },
  { id: "decision-log", label: "Decision Log" },
];

const VIEW_TOGGLE_ACTIVE =
  "rounded-md bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-100 shadow-sm";
const VIEW_TOGGLE_INACTIVE =
  "rounded-md px-3 py-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-300";

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

function hubEntriesMatchingQuery(entries: DocHubEntry[], query: string): DocHubEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return entries;
  return entries.filter((doc) => {
    const haystack = [
      doc.title,
      doc.summary,
      doc.slug,
      doc.tags.join(" "),
      doc.owners.join(" "),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

export type DocsHubClientProps = {
  entries: DocHubEntry[];
  readingPaths: ReadingPathClient[];
};

export function DocsHubClient({ entries, readingPaths }: DocsHubClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryRaw = searchParams.get("q") ?? "";
  const queryTrimmed = queryRaw.trim();
  const searchActive = queryTrimmed.length > 0;

  const view: "category" | "persona" =
    searchParams.get("view") === "persona" ? "persona" : "category";

  const setView = (next: "category" | "persona") => {
    const params = new URLSearchParams(searchParams.toString());
    if (next === "category") {
      params.delete("view");
    } else {
      params.set("view", "persona");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };

  const [activeFilter, setActiveFilter] = useState<HubDocCategory | "all">("all");

  const filtered = useMemo(() => {
    if (activeFilter === "all") return entries;
    return entries.filter((e) => e.hubCategory === activeFilter);
  }, [entries, activeFilter]);

  const searchHits = useMemo(
    () => hubEntriesMatchingQuery(entries, queryTrimmed),
    [entries, queryTrimmed],
  );

  const personaDocs = useMemo(
    () =>
      filtered.map((e) => ({
        slug: e.slug,
        title: e.title,
        summary: e.summary,
        category: e.hubCategory,
        owners: e.owners,
      })),
    [filtered],
  );

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

      <Link
        href="/admin/docs/day-0-founder-actions"
        className="block rounded-xl border border-emerald-900/40 bg-emerald-950/20 p-4 transition-colors hover:bg-emerald-950/30"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">
              Founder Quick Start
            </p>
            <h2 className="mt-1 text-lg font-semibold text-zinc-100">Day-0 founder actions</h2>
            <p className="mt-1 text-sm text-zinc-400">
              First-day checklist: keys, accounts, dispatches, reviews.
            </p>
          </div>
          <ArrowRight className="h-5 w-5 shrink-0 text-emerald-400" />
        </div>
      </Link>

      <div className="mb-4 inline-flex rounded-lg border border-zinc-800 p-1">
        <button
          type="button"
          data-testid="docs-hub-view-category"
          aria-pressed={view === "category"}
          onClick={() => setView("category")}
          className={view === "category" ? VIEW_TOGGLE_ACTIVE : VIEW_TOGGLE_INACTIVE}
        >
          By category
        </button>
        <button
          type="button"
          data-testid="docs-hub-view-persona"
          aria-pressed={view === "persona"}
          onClick={() => setView("persona")}
          className={view === "persona" ? VIEW_TOGGLE_ACTIVE : VIEW_TOGGLE_INACTIVE}
        >
          By persona
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <DocsHubSearchForm />
        <Link
          href="/admin/docs/graph"
          className="inline-flex items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900/50 px-3 py-2 text-xs font-medium text-zinc-200 transition hover:border-sky-500/40 hover:bg-zinc-800/80 hover:text-white"
        >
          Knowledge graph
        </Link>
      </div>

      <section aria-labelledby="reading-paths-heading" className="space-y-3">
        <div className="flex items-center gap-2">
          <Route className="h-4 w-4 text-sky-400" />
          <h2 id="reading-paths-heading" className="text-sm font-semibold text-zinc-200">
            Reading paths
          </h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {readingPaths.map((p) => (
            <ReadingPathCard key={p.id} {...p} />
          ))}
        </div>
      </section>

      {searchActive ? (
        <section data-testid="docs-hub-search-results" className="space-y-3">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
            Search results
          </p>
          <p className="text-xs text-zinc-500">
            {searchHits.length} result{searchHits.length === 1 ? "" : "s"} for &ldquo;{queryTrimmed}
            &rdquo;
          </p>
          {searchHits.length === 0 ? (
            <p className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400">
              No docs matched your query.
            </p>
          ) : (
            <div className="grid gap-2 md:grid-cols-2">
              {searchHits.map((doc) => (
                <Link
                  key={doc.slug}
                  href={`/admin/docs/${doc.slug}`}
                  className="rounded-lg border border-zinc-800/70 bg-zinc-950/40 p-3 transition hover:border-zinc-700 hover:bg-zinc-900"
                >
                  <p className="text-sm font-medium text-zinc-100">{doc.title}</p>
                  <p className="mt-1 text-xs text-zinc-400">{doc.summary}</p>
                </Link>
              ))}
            </div>
          )}
        </section>
      ) : view === "persona" ? (
        <DocsHubPersonaView docs={personaDocs} />
      ) : (
        <>
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
                    data-testid={
                      f.id === "all" ? "docs-hub-filter-all" : `docs-hub-filter-${f.id}`
                    }
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
                <Link
                  key={doc.slug}
                  href={`/admin/docs/${doc.slug}`}
                  data-testid="docs-hub-card"
                  data-hub-category={doc.hubCategory}
                  className="group flex flex-col rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 transition hover:border-zinc-700 hover:bg-zinc-900/70"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <span className="text-sm font-semibold text-zinc-100 group-hover:text-white">
                      {doc.title}
                    </span>
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
                </Link>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
