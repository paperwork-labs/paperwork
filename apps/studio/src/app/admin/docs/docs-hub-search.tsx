"use client";

import { useState } from "react";
import { Loader2, Search } from "lucide-react";

/** F-051 — visible busy state while GET navigates to search results. */
export function DocsHubSearchForm() {
  const [pending, setPending] = useState(false);

  return (
    <form
      action="/admin/docs/search"
      method="GET"
      onSubmit={() => setPending(true)}
      className="flex max-w-xl items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2"
    >
      <Search className="h-4 w-4 shrink-0 text-zinc-500" />
      <input
        type="text"
        name="q"
        placeholder="Search titles, tags, owners…"
        className="min-w-0 flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
        disabled={pending}
      />
      <button
        type="submit"
        disabled={pending}
        className="inline-flex items-center gap-1.5 rounded-md bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-200 transition hover:bg-zinc-700 disabled:opacity-50"
      >
        {pending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
        Search
      </button>
    </form>
  );
}
