"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, ChevronDown, RefreshCw, Search, X } from "lucide-react";
import { Badge } from "@paperwork-labs/ui";
import { Button } from "@paperwork-labs/ui";
import { Input } from "@paperwork-labs/ui";
import { Skeleton } from "@paperwork-labs/ui";
import {
  type AppLogEntry,
  type LogSeverity,
  type LogsQueryParams,
  SEVERITY_LEVELS,
  fetchLogs,
  severityColorClass,
} from "@/lib/app-logs";

const AUTO_REFRESH_MS = 30_000;
const PAGE_SIZE = 50;

function SeverityBadge({ severity }: { severity: LogSeverity }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${severityColorClass(severity)}`}
    >
      {severity}
    </span>
  );
}

function SourceBadge({ source }: { source: AppLogEntry["source"] }) {
  const cls =
    source === "push"
      ? "bg-violet-950/50 text-violet-300 border-violet-800/50"
      : source === "vercel-pull"
        ? "bg-zinc-800 text-zinc-300 border-zinc-700"
        : "bg-zinc-800 text-zinc-300 border-zinc-700";
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] ${cls}`}
    >
      {source}
    </span>
  );
}

function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
      timeZone: "America/Los_Angeles",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function LogRow({ entry }: { entry: AppLogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const hasAttrs = Object.keys(entry.attrs).length > 0;

  return (
    <div className="border-b border-zinc-800/60 px-4 py-2.5 hover:bg-zinc-900/40">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 shrink-0">
          <SeverityBadge severity={entry.severity} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <span className="font-mono text-zinc-400">{entry.app}</span>
            <span>·</span>
            <span className="font-mono">{entry.service}</span>
            <span>·</span>
            <span>{formatTime(entry.occurred_at)}</span>
            <SourceBadge source={entry.source} />
          </div>
          <p className="mt-1 font-mono text-sm leading-snug text-zinc-200 break-all">
            {entry.message}
          </p>
          {hasAttrs && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="mt-1 flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300"
              aria-expanded={expanded}
            >
              <ChevronDown
                className={`h-3 w-3 transition-transform ${expanded ? "rotate-180" : ""}`}
              />
              {expanded ? "Hide" : "Show"} attrs
            </button>
          )}
          {expanded && hasAttrs && (
            <pre className="mt-2 overflow-x-auto rounded bg-zinc-950 p-2 text-xs text-zinc-300">
              {JSON.stringify(entry.attrs, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? "border-zinc-400 bg-zinc-700 text-zinc-100"
          : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300"
      }`}
    >
      {label}
    </button>
  );
}

export default function LogsTab() {
  const [entries, setEntries] = useState<AppLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [totalMatched, setTotalMatched] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const [severityFilter, setSeverityFilter] = useState<LogSeverity | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const buildParams = useCallback(
    (cursor?: string): LogsQueryParams => ({
      severity: severityFilter ?? undefined,
      q: debouncedSearch || undefined,
      limit: PAGE_SIZE,
      cursor,
    }),
    [severityFilter, debouncedSearch],
  );

  const load = useCallback(
    async (opts: { reset?: boolean; silent?: boolean } = {}) => {
      if (!opts.silent) {
        if (opts.reset) setLoading(true);
        else setRefreshing(true);
      }
      setError(null);
      try {
        const result = await fetchLogs(buildParams());
        setEntries(result.logs);
        setNextCursor(result.next_cursor);
        setTotalMatched(result.total_matched);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load logs");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [buildParams],
  );

  // Reset on filter change
  useEffect(() => {
    void load({ reset: true });
  }, [load]);

  // Debounce search input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchQuery]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => void load({ silent: true }), AUTO_REFRESH_MS);
    return () => clearInterval(interval);
  }, [autoRefresh, load]);

  const loadMore = async () => {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const result = await fetchLogs(buildParams(nextCursor));
      setEntries((prev) => [...prev, ...result.logs]);
      setNextCursor(result.next_cursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load more");
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-200">Application Logs</h2>
          <p className="mt-0.5 text-xs text-zinc-500">
            Brain-owned log store — no third-party vendor. Apps push events; Brain pulls Vercel +
            Render hourly.
            {totalMatched != null && (
              <span className="ml-1 text-zinc-400">{totalMatched.toLocaleString()} matched.</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAutoRefresh((v) => !v)}
            className={`text-xs ${autoRefresh ? "text-emerald-400" : "text-zinc-500"}`}
            aria-pressed={autoRefresh}
            aria-label={autoRefresh ? "Disable auto-refresh" : "Enable auto-refresh"}
          >
            {autoRefresh ? "Live" : "Paused"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void load()}
            disabled={refreshing}
            aria-label="Refresh logs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Severity chips */}
        <FilterChip
          label="All"
          active={severityFilter === null}
          onClick={() => setSeverityFilter(null)}
        />
        {SEVERITY_LEVELS.map((s) => (
          <FilterChip
            key={s}
            label={s}
            active={severityFilter === s}
            onClick={() => setSeverityFilter(s)}
          />
        ))}

        {/* Search */}
        <div className="relative ml-auto flex items-center">
          <Search className="absolute left-2.5 h-3.5 w-3.5 text-zinc-500" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search messages…"
            className="h-7 w-52 rounded-md bg-zinc-900 pl-8 pr-7 text-xs text-zinc-200 placeholder:text-zinc-600 focus:ring-1 focus:ring-zinc-600"
            aria-label="Search log messages"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 text-zinc-500 hover:text-zinc-300"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-900/50 bg-rose-950/30 p-3 text-sm text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Log list */}
      <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50">
        {loading ? (
          <div className="space-y-3 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-start gap-3">
                <Skeleton className="mt-0.5 h-5 w-14 rounded" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3 w-40 rounded" />
                  <Skeleton className="h-4 w-full rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-zinc-500">
            <Search className="h-6 w-6 opacity-40" />
            <p className="text-sm">No logs found</p>
            <p className="text-xs">
              {severityFilter || debouncedSearch
                ? "Try loosening your filters."
                : "Logs appear here once apps push events or Brain pulls from Vercel/Render."}
            </p>
          </div>
        ) : (
          <div>
            {entries.map((entry) => (
              <LogRow key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {nextCursor && !loading && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadMore()}
            disabled={loadingMore}
            className="text-xs"
          >
            {loadingMore ? "Loading…" : "Load more"}
          </Button>
        </div>
      )}
    </div>
  );
}
