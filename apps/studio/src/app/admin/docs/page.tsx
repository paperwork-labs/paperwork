import Link from "next/link";
import { AlertTriangle, BookOpen, Lock } from "lucide-react";

import { DocsHubSearchForm } from "./docs-hub-search";
import { groupDocsByCategory, type DocCategory } from "@/lib/docs";

export const dynamic = "force-static";
export const revalidate = 300;

const categoryIcon: Record<DocCategory, string> = {
  philosophy: "Philosophy",
  architecture: "Architecture",
  runbooks: "Runbooks",
  reference: "Reference",
  plans: "Plans",
  sprints: "Sprints",
  generated: "Generated",
};

export default function DocsHubPage() {
  const { categories, byCategory } = groupDocsByCategory();

  const orderedCategories = [...categories].sort((a, b) => a.order - b.order);

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <div className="flex items-center gap-3">
          <BookOpen className="h-5 w-5 text-sky-300" />
          <h1 className="text-xl font-semibold text-zinc-100">Docs</h1>
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
            agent-readable
          </span>
        </div>
        <p className="max-w-3xl text-sm text-zinc-400">
          One place for every persona to find the philosophy, architecture,
          runbooks, and specs that govern Paperwork Labs. Philosophy docs are
          CODEOWNERS-locked — they don&apos;t change without explicit sign-off.
          Anything under <span className="text-zinc-300">/admin/docs/&lt;slug&gt;</span> is readable by
          agents for grounded responses.
        </p>
        <DocsHubSearchForm />
      </header>

      {orderedCategories.map((cat) => {
        const docs = byCategory[cat.id] ?? [];
        if (docs.length === 0) return null;
        const isImmutable = cat.id === "philosophy";
        return (
          <section
            key={cat.id}
            className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
          >
            <div className="mb-3 flex items-center gap-2">
              <h2 className="text-sm font-semibold text-zinc-100">
                {categoryIcon[cat.id] ?? cat.label}
              </h2>
              {isImmutable ? (
                <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
                  <Lock className="h-3 w-3" />
                  immutable
                </span>
              ) : null}
              <span className="text-[10px] uppercase tracking-wide text-zinc-500">
                {docs.length} docs
              </span>
            </div>
            <p className="mb-4 text-xs text-zinc-500">{cat.description}</p>
            <div className="grid gap-2 md:grid-cols-2">
              {docs.map((doc) => (
                <Link
                  key={doc.slug}
                  href={`/admin/docs/${doc.slug}`}
                  className="group rounded-lg border border-zinc-800/70 bg-zinc-950/40 p-3 transition hover:border-zinc-700 hover:bg-zinc-900"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-zinc-100 group-hover:text-white">
                      {doc.title}
                    </p>
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
                  <p className="mt-1 text-xs text-zinc-400">{doc.summary}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {doc.owners.map((owner) => (
                      <span
                        key={owner}
                        className="rounded-full bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-medium text-sky-300"
                      >
                        {owner}
                      </span>
                    ))}
                    {doc.tags.slice(0, 4).map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
