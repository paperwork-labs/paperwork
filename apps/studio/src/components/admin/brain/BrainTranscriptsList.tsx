"use client";

import Link from "next/link";
import { RefreshCw } from "lucide-react";

import { useBrainTranscripts } from "@/hooks/useBrainTranscripts";
import { Button, Skeleton } from "@paperwork-labs/ui";

function ListSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={String(i)} className="h-14 w-full rounded-lg bg-zinc-800/80" />
      ))}
    </div>
  );
}

export function BrainTranscriptsList() {
  const { loading, data, error, retry, loadMore, loadingMore } = useBrainTranscripts();

  if (loading && !data) {
    return <ListSkeleton />;
  }

  if (error && !data) {
    return (
      <div
        className="rounded-xl border border-rose-900/40 bg-rose-500/5 p-6"
        role="alert"
      >
        <p className="text-sm font-medium text-rose-300">Could not load transcripts</p>
        <p className="mt-1 text-xs text-rose-500/80">{error.message}</p>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          className="mt-5 min-h-11 px-6"
          onClick={() => retry()}
        >
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden />
          Retry
        </Button>
      </div>
    );
  }

  if (!data) {
    return (
      <div
        className="rounded-xl border border-rose-900/40 bg-rose-500/5 p-6"
        role="alert"
      >
        <p className="text-sm font-medium text-rose-300">Unexpected empty response</p>
        <p className="mt-1 text-xs text-rose-500/80">
          The transcript list finished loading but returned no payload. Retry or check Brain logs.
        </p>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          className="mt-5 min-h-11 px-6"
          onClick={() => retry()}
        >
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden />
          Retry
        </Button>
      </div>
    );
  }

  if (data.items.length === 0) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-10 text-center">
        <p className="text-sm font-medium text-zinc-300">No transcripts yet</p>
        <p className="mt-2 text-xs text-zinc-500">
          Nothing ingested for this Brain environment. From a dev machine with your Cursor{" "}
          <span className="font-mono text-zinc-400">agent-transcripts</span> tree, run{" "}
          <span className="font-mono text-zinc-400">pnpm run backfill:transcripts</span> (see
          Operator panel above).
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error ? (
        <div
          className="rounded-lg border border-amber-900/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
          role="status"
        >
          <span className="font-medium">Pagination paused — </span>
          {error.message}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-3 mt-3 inline-flex min-h-11 sm:ml-4 sm:mt-0"
            onClick={() => retry()}
          >
            Reload list
          </Button>
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40">
        <table className="w-full min-w-[640px] text-left text-sm text-zinc-300">
          <thead className="border-b border-zinc-800 bg-zinc-950/40 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            <tr>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Messages</th>
              <th className="hidden px-4 py-3 md:table-cell">Started</th>
              <th className="hidden px-4 py-3 lg:table-cell">Ended</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <tr key={row.id} className="border-b border-zinc-800/80 last:border-b-0">
                <td className="px-0 align-top">
                  <Link
                    href={`/admin/transcripts/${encodeURIComponent(row.id)}`}
                    className="flex min-h-11 flex-col justify-center px-4 py-3 text-zinc-100 hover:bg-zinc-800/50 hover:text-white motion-safe:transition-colors"
                  >
                    <span className="line-clamp-2 font-medium">{row.title}</span>
                    {row.tags.length > 0 ? (
                      <span className="mt-1 text-[11px] font-normal text-zinc-500">
                        {row.tags.join(" · ")}
                      </span>
                    ) : null}
                  </Link>
                </td>
                <td className="px-4 py-3 align-middle tabular-nums text-zinc-400">
                  {row.message_count}
                </td>
                <td className="hidden px-4 py-3 align-middle text-xs text-zinc-500 md:table-cell">
                  {row.started_at}
                </td>
                <td className="hidden px-4 py-3 align-middle text-xs text-zinc-500 lg:table-cell">
                  {row.ended_at}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.next_cursor ? (
        <Button
          type="button"
          variant="secondary"
          className="min-h-11 w-full sm:w-auto"
          disabled={loadingMore}
          onClick={() => void loadMore()}
        >
          {loadingMore ? "Loading…" : "Load more"}
        </Button>
      ) : null}
    </div>
  );
}
