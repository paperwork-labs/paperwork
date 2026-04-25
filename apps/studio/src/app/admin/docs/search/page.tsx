import Link from "next/link";
import { ArrowLeft, Search } from "lucide-react";

import { searchDocs } from "@/lib/docs";

export const dynamic = "force-dynamic";

type Params = { searchParams: Promise<{ q?: string }> };

export default async function DocsSearchPage({ searchParams }: Params) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();
  const hits = query ? searchDocs(query) : [];

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-2 text-xs text-zinc-500">
        <Link href="/admin/docs" className="flex items-center gap-1 hover:text-zinc-200">
          <ArrowLeft className="h-3.5 w-3.5" />
          All docs
        </Link>
      </nav>

      <header className="space-y-3">
        <h1 className="text-xl font-semibold text-zinc-100">Search docs</h1>
        <form
          action="/admin/docs/search"
          method="GET"
          className="flex max-w-xl items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2"
        >
          <Search className="h-4 w-4 text-zinc-500" />
          <input
            type="text"
            name="q"
            defaultValue={query}
            placeholder="Search titles, tags, owners…"
            className="flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
          />
          <button
            type="submit"
            className="rounded-md bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-200 transition hover:bg-zinc-700"
          >
            Search
          </button>
        </form>
      </header>

      {query ? (
        <section className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-zinc-500">
            {hits.length} results for &ldquo;{query}&rdquo;
          </p>
          {hits.length === 0 ? (
            <p className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400">
              No docs matched &ldquo;{query}&rdquo;. Try a broader term or check the
              full list on{" "}
              <Link href="/admin/docs" className="text-sky-400 hover:underline">
                /admin/docs
              </Link>
              .
            </p>
          ) : (
            <div className="grid gap-2 md:grid-cols-2">
              {hits.map((doc) => (
                <Link
                  key={doc.slug}
                  href={`/admin/docs/${doc.slug}`}
                  className="rounded-lg border border-zinc-800/70 bg-zinc-950/40 p-3 transition hover:border-zinc-700 hover:bg-zinc-900"
                >
                  <p className="text-sm font-medium text-zinc-100">{doc.title}</p>
                  <p className="mt-1 text-xs text-zinc-400">{doc.summary}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
                      {doc.category}
                    </span>
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
          )}
        </section>
      ) : (
        <p className="text-sm text-zinc-400">
          Enter a query above to search every doc in{" "}
          <code className="text-zinc-300">docs/_index.yaml</code>.
        </p>
      )}
    </div>
  );
}
