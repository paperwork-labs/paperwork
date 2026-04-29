"use client";

import { type ReactNode, useState, useEffect, useCallback, useRef } from "react";
import { RefreshCw, ChevronDown, ChevronRight, Search } from "lucide-react";

// ---------------------------------------------------------------------------
// Types (mirrored from Brain schema)
// ---------------------------------------------------------------------------

type AppName = "studio" | "axiomfolio" | "filefree" | "launchfree" | "distill" | "brain";
type Severity = "debug" | "info" | "warn" | "error" | "critical";
type LogSource = "push" | "pull";

interface AppLog {
  id: string;
  app: AppName;
  service: string;
  severity: Severity;
  message: string;
  metadata: Record<string, unknown>;
  request_id: string | null;
  at: string;
  source: LogSource;
}

interface LogsResponse {
  logs: AppLog[];
  total_matched: number;
  next_cursor: string | null;
  last_pulled_at: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const APP_FILTERS: Array<{ value: AppName | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "studio", label: "Studio" },
  { value: "axiomfolio", label: "Axiomfolio" },
  { value: "filefree", label: "FileFree" },
  { value: "launchfree", label: "LaunchFree" },
  { value: "distill", label: "Distill" },
  { value: "brain", label: "Brain" },
];

const SEV_FILTERS: Array<{ value: Severity | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "info", label: "info" },
  { value: "warn", label: "warn" },
  { value: "error", label: "error" },
  { value: "critical", label: "critical" },
];

const TIME_RANGES: Array<{ value: string; label: string; hours: number }> = [
  { value: "1h", label: "1h", hours: 1 },
  { value: "24h", label: "24h", hours: 24 },
  { value: "7d", label: "7d", hours: 168 },
  { value: "30d", label: "30d", hours: 720 },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEV_DOT: Record<Severity, string> = {
  debug: "bg-zinc-500",
  info: "bg-blue-500",
  warn: "bg-amber-500",
  error: "bg-rose-500",
  critical: "bg-red-600",
};

const SEV_TEXT: Record<Severity, string> = {
  debug: "text-zinc-400",
  info: "text-blue-400",
  warn: "text-amber-400",
  error: "text-rose-400",
  critical: "text-red-400",
};

const APP_BADGE_COLOR: Record<AppName, string> = {
  studio: "bg-indigo-900/40 text-indigo-300 border-indigo-700/30",
  axiomfolio: "bg-emerald-900/40 text-emerald-300 border-emerald-700/30",
  filefree: "bg-sky-900/40 text-sky-300 border-sky-700/30",
  launchfree: "bg-violet-900/40 text-violet-300 border-violet-700/30",
  distill: "bg-orange-900/40 text-orange-300 border-orange-700/30",
  brain: "bg-zinc-800/60 text-zinc-300 border-zinc-700/30",
};

function relativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  } catch {
    return iso;
  }
}

function sinceIso(hours: number): string {
  return new Date(Date.now() - hours * 3600 * 1000).toISOString();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? "bg-zinc-100 text-zinc-900"
          : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
      }`}
    >
      {children}
    </button>
  );
}

function SeverityDot({ severity }: { severity: Severity }) {
  return (
    <span
      className={`mt-1 h-2 w-2 shrink-0 rounded-full ${SEV_DOT[severity]}`}
      aria-label={severity}
    />
  );
}

function LogRow({ log }: { log: AppLog }) {
  const [expanded, setExpanded] = useState(false);
  const hasMetadata = Object.keys(log.metadata).length > 0;

  return (
    <div className="border-b border-zinc-800/60 px-4 py-3 last:border-b-0">
      <div
        className="flex cursor-pointer items-start gap-3"
        onClick={() => setExpanded((p) => !p)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setExpanded((p) => !p);
        }}
        aria-expanded={expanded}
      >
        <SeverityDot severity={log.severity} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded border px-1.5 py-0.5 text-xs font-medium ${APP_BADGE_COLOR[log.app]}`}
            >
              {log.app}
            </span>
            <span className="text-xs text-zinc-500">{log.service}</span>
            <span className={`text-xs font-medium ${SEV_TEXT[log.severity]}`}>
              {log.severity}
            </span>
          </div>
          <p className="mt-1 truncate text-sm text-zinc-200">{log.message}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <time
            dateTime={log.at}
            title={log.at}
            className="whitespace-nowrap text-xs text-zinc-500"
          >
            {relativeTime(log.at)}
          </time>
          {hasMetadata &&
            (expanded ? (
              <ChevronDown className="h-3 w-3 text-zinc-500" />
            ) : (
              <ChevronRight className="h-3 w-3 text-zinc-500" />
            ))}
        </div>
      </div>

      {expanded && (
        <div className="ml-5 mt-2 space-y-1">
          {log.request_id && (
            <p className="font-mono text-xs text-zinc-500">
              request_id: <span className="text-zinc-400">{log.request_id}</span>
            </p>
          )}
          <p className="font-mono text-xs text-zinc-500">
            source: <span className="text-zinc-400">{log.source}</span>
          </p>
          <p className="font-mono text-xs text-zinc-500">
            at: <span className="text-zinc-400">{log.at}</span>
          </p>
          {hasMetadata && (
            <pre className="mt-2 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-300">
              {JSON.stringify(log.metadata, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Logs Tab
// ---------------------------------------------------------------------------

export default function LogsTab() {
  const [appFilter, setAppFilter] = useState<AppName | "all">("all");
  const [sevFilter, setSevFilter] = useState<Severity | "all">("all");
  const [timeRange, setTimeRange] = useState<string>("24h");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [logs, setLogs] = useState<AppLog[]>([]);
  const [totalMatched, setTotalMatched] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [lastPulledAt, setLastPulledAt] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isPulling, setIsPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedAll, setLoadedAll] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search input 300ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search]);

  const hours = TIME_RANGES.find((t) => t.value === timeRange)?.hours ?? 24;

  const buildUrl = useCallback(
    (cursor?: string | null) => {
      const params = new URLSearchParams({ limit: "50" });
      if (appFilter !== "all") params.set("app", appFilter);
      if (sevFilter !== "all") params.set("severity", sevFilter);
      if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());
      params.set("since", sinceIso(hours));
      if (cursor) params.set("cursor", cursor);
      return `/api/admin/logs?${params.toString()}`;
    },
    [appFilter, sevFilter, debouncedSearch, hours],
  );

  const load = useCallback(
    async (reset = true) => {
      setIsLoading(true);
      if (reset) {
        setError(null);
        setLogs([]);
        setNextCursor(null);
        setLoadedAll(false);
      }
      try {
        const url = buildUrl(reset ? null : nextCursor);
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) {
          setError(`Brain API returned ${res.status}`);
          return;
        }
        const body = (await res.json()) as { success?: boolean; data?: LogsResponse };
        const data = body.data;
        if (!data) {
          setError("Unexpected response from Brain API");
          return;
        }
        setLogs((prev) => (reset ? data.logs : [...prev, ...data.logs]));
        setTotalMatched(data.total_matched);
        setNextCursor(data.next_cursor ?? null);
        setLastPulledAt(data.last_pulled_at ?? {});
        if (!data.next_cursor) setLoadedAll(true);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch logs");
      } finally {
        setIsLoading(false);
      }
    },
    [buildUrl, nextCursor],
  );

  // Reset and reload when filters change
  useEffect(() => {
    void load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appFilter, sevFilter, debouncedSearch, timeRange]);

  const handleManualRefresh = useCallback(() => void load(true), [load]);

  const handlePull = useCallback(async () => {
    setIsPulling(true);
    try {
      const res = await fetch("/api/admin/logs/pull", { method: "POST", cache: "no-store" });
      if (!res.ok) {
        setError(`Pull failed: HTTP ${res.status}`);
        return;
      }
      await load(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pull failed");
    } finally {
      setIsPulling(false);
    }
  }, [load]);

  const handleLoadMore = useCallback(() => void load(false), [load]);

  // Last pulled label
  const lastPulledLabel = (() => {
    const entries = Object.values(lastPulledAt);
    if (!entries.length) return "Never";
    const latest = entries.reduce((a, b) => (a > b ? a : b));
    return relativeTime(latest);
  })();

  return (
    <section aria-label="Application Logs" className="space-y-4">
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span>
            Last pulled:{" "}
            <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 font-medium text-zinc-300">
              {lastPulledLabel}
            </span>
          </span>
          <button
            onClick={handleManualRefresh}
            disabled={isLoading}
            aria-label="Refresh logs"
            className="inline-flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-zinc-400 transition hover:bg-zinc-700 hover:text-zinc-200 disabled:cursor-wait disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={handlePull}
            disabled={isPulling}
            aria-label="Pull logs from Vercel and Render"
            className="inline-flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-zinc-400 transition hover:bg-zinc-700 hover:text-zinc-200 disabled:cursor-wait disabled:opacity-50"
          >
            {isPulling ? "Pulling…" : "Pull now"}
          </button>
        </div>

        {/* Time range */}
        <div className="flex items-center gap-1">
          {TIME_RANGES.map((tr) => (
            <FilterChip
              key={tr.value}
              active={timeRange === tr.value}
              onClick={() => setTimeRange(tr.value)}
            >
              {tr.label}
            </FilterChip>
          ))}
        </div>
      </div>

      {/* App filters */}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by app">
        {APP_FILTERS.map((f) => (
          <FilterChip
            key={f.value}
            active={appFilter === f.value}
            onClick={() => setAppFilter(f.value as AppName | "all")}
          >
            {f.label}
          </FilterChip>
        ))}
      </div>

      {/* Severity sub-filters */}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by severity">
        {SEV_FILTERS.map((f) => (
          <FilterChip
            key={f.value}
            active={sevFilter === f.value}
            onClick={() => setSevFilter(f.value as Severity | "all")}
          >
            {f.label}
          </FilterChip>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search message and metadata…"
          aria-label="Search logs"
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 py-2 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
        />
      </div>

      {/* Count */}
      {!isLoading && !error && (
        <p className="text-xs text-zinc-500">
          {totalMatched === 0
            ? "No logs match this filter"
            : `${totalMatched.toLocaleString()} log${totalMatched === 1 ? "" : "s"} matched`}
        </p>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-xl border border-rose-800/30 bg-rose-900/10 px-4 py-3 text-sm text-rose-400">
          {error}
        </div>
      )}

      {/* Log list */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
        {isLoading && logs.length === 0 ? (
          <div className="space-y-0 divide-y divide-zinc-800/40">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-3">
                <div className="mt-1 h-2 w-2 shrink-0 animate-pulse rounded-full bg-zinc-700" />
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="h-3 w-1/4 animate-pulse rounded bg-zinc-800" />
                  <div className="h-3 w-3/4 animate-pulse rounded bg-zinc-800" />
                </div>
              </div>
            ))}
          </div>
        ) : logs.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-sm text-zinc-500">
              No logs match this filter — try widening the time range
            </p>
          </div>
        ) : (
          <div>
            {logs.map((log) => (
              <LogRow key={log.id} log={log} />
            ))}

            {/* Load more */}
            {!loadedAll && (
              <div className="border-t border-zinc-800 px-4 py-3 text-center">
                <button
                  onClick={handleLoadMore}
                  disabled={isLoading}
                  className="text-xs text-zinc-500 transition hover:text-zinc-300 disabled:cursor-wait"
                >
                  {isLoading ? "Loading…" : "Load more"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
