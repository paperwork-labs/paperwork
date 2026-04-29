/**
 * Typed client for Brain-owned application logs API (WS-69 PR M).
 *
 * All requests go through Brain's admin endpoints which require X-Brain-Secret.
 * In the browser these calls hit Studio's /api/admin/app-logs route which
 * proxies with the secret server-side.
 */

export type LogSeverity = "debug" | "info" | "warn" | "error" | "critical";

export interface AppLogEntry {
  id: string;
  app: string;
  service: string;
  severity: LogSeverity;
  message: string;
  attrs: Record<string, string | number | boolean | null>;
  source: "push" | "vercel-pull" | "render-pull";
  occurred_at: string; // ISO-8601
  ingested_at: string; // ISO-8601
}

export interface LogsQueryResult {
  logs: AppLogEntry[];
  next_cursor: string | null;
  total_matched: number;
}

export interface LogsQueryParams {
  app?: string;
  service?: string;
  severity?: LogSeverity;
  since?: string;
  until?: string;
  q?: string;
  cursor?: string;
  limit?: number;
}

/** Build query string from non-null params. */
function toQueryString(params: LogsQueryParams): string {
  const p = new URLSearchParams();
  if (params.app) p.set("app", params.app);
  if (params.service) p.set("service", params.service);
  if (params.severity) p.set("severity", params.severity);
  if (params.since) p.set("since", params.since);
  if (params.until) p.set("until", params.until);
  if (params.q) p.set("q", params.q);
  if (params.cursor) p.set("cursor", params.cursor);
  if (params.limit != null) p.set("limit", String(params.limit));
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** Fetch logs from the Studio proxy route. */
export async function fetchLogs(params: LogsQueryParams = {}): Promise<LogsQueryResult> {
  const qs = toQueryString(params);
  const res = await fetch(`/api/admin/app-logs${qs}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(`app-logs API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<LogsQueryResult>;
}

/** Map severity to a Tailwind CSS color class for badges. */
export function severityColorClass(severity: LogSeverity): string {
  switch (severity) {
    case "debug":
      return "bg-zinc-800 text-zinc-400 border-zinc-700";
    case "info":
      return "bg-sky-950/60 text-sky-300 border-sky-800/50";
    case "warn":
      return "bg-amber-950/60 text-amber-300 border-amber-800/50";
    case "error":
      return "bg-rose-950/60 text-rose-300 border-rose-800/50";
    case "critical":
      return "bg-red-950 text-red-200 border-red-700";
  }
}

export const SEVERITY_LEVELS: LogSeverity[] = ["debug", "info", "warn", "error", "critical"];
