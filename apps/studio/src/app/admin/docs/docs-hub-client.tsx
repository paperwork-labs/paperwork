"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Route } from "lucide-react";

import { DocsHubDocCard } from "./docs-hub-doc-card";
import { DocsHubPersonaView } from "./docs-hub-persona-view";
import { DocsHubSearchForm } from "./docs-hub-search";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import type { DocHubEntry } from "@/lib/docs";
import { filterHubEntriesByQuery } from "@/lib/docs";
import type { HubDocCategory } from "@/lib/doc-metadata";

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

export type DocsHubClientProps = {
  entries: DocHubEntry[];
  readingPaths: ReadingPathClient[];
};

export function DocsHubClient({ entries, readingPaths }: DocsHubClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const q = (searchParams.get("q") ?? "").trim();
  const hasSearchQuery = q.length > 0;
  const view: "category" | "persona" =
    searchParams.get("view") === "persona" ? "persona" : "category";

  const [activeFilter, setActiveFilter] = useState<HubDocCategory | "all">("all");

  const filtered = useMemo(() => {
    if (activeFilter === "all") return entries;
    return entries.filter((e) => e.hubCategory === activeFilter);
  }, [entries, activeFilter]);

  const searchHits = useMemo(() => filterHubEntriesByQuery(entries, q), [entries, q]);

  const setHubView = (next: "category" | "persona") => {
    const params = new URLSearchParams(searchParams.toString());
    if (next === "category") {
      params.delete("view");
    } else {
      params.set("view", "persona");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

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

      {!hasSearchQuery && view === "category" ? (
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
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <DocsHubSearchForm defaultQuery={q} hubView={view} />
        <Link
          href="/admin/docs/graph"
          className="inline-flex items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900/50 px-3 py-2 text-xs font-medium text-zinc-200 transition hover:border-sky-500/40 hover:bg-zinc-800/80 hover:text-white"
        >
          Knowledge graph
        </Link>
      </div>

      {!hasSearchQuery ? (
        <div className="mb-4 inline-flex rounded-lg border border-zinc-800 p-1">
          <button
            type="button"
            data-testid="docs-hub-view-toggle-category"
            data-active={view === "category"}
            onClick={() => setHubView("category")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              view === "category"
                ? "bg-zinc-800 text-zinc-100 shadow-sm"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            By category
          </button>
          <button
            type="button"
            data-testid="docs-hub-view-toggle-persona"
            data-active={view === "persona"}
            onClick={() => setHubView("persona")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              view === "persona"
                ? "bg-zinc-800 text-zinc-100 shadow-sm"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            By persona
          </button>
        </div>
      ) : null}

      {hasSearchQuery ? (
        <section className="space-y-3" aria-live="polite">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
            Search results
          </p>
          <p className="text-xs text-zinc-500">
            {searchHits.length} result{searchHits.length === 1 ? "" : "s"} for &ldquo;{q}&rdquo;
          </p>
          {searchHits.length === 0 ? (
            <p className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400">
              No docs matched. Try another term or browse the full hub.
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {searchHits.map((doc: DocHubEntry) => (
                <DocsHubDocCard key={doc.slug} doc={doc} />
              ))}
            </div>
          )}
        </section>
      ) : view === "category" ? (
        <>
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
            <div className="flex flex-wrap gap-2" role="group" aria-label="Doc category filters">
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
            {filtered.map((doc) => (
              <DocsHubDocCard key={doc.slug} doc={doc} />
            ))}
          </div>
        </>
      ) : (
        <DocsHubPersonaView entries={entries} />
      )}
    </div>
  );
}
