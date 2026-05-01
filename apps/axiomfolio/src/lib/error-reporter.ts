/**
 * Forward client failures to Brain via `/api/admin/error-report`.
 */

export type ErrorReportPayload = {
  source: string;
  summary: string;
  fingerprint: string;
  environment?: string;
  severity?: "info" | "warning" | "error" | "critical";
  url?: string | null;
  user_agent?: string | null;
  stack?: string | null;
  metadata?: Record<string, unknown> | null;
};

export function errorFingerprint(parts: {
  source: string;
  message: string;
  stack?: string;
  url?: string;
}): string {
  const raw = `${parts.source}|${parts.message}|${parts.stack ?? ""}|${parts.url ?? ""}`;
  let h = 0;
  for (let i = 0; i < raw.length; i++) h = (Math.imul(31, h) + raw.charCodeAt(i)) | 0;
  return `fp:${parts.source}:${(h >>> 0).toString(16)}`.slice(0, 200);
}

export async function reportError(payload: ErrorReportPayload): Promise<void> {
  try {
    await fetch("/api/admin/error-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch (e) {
    console.error("[error-reporter] failed to POST error report.", e);
  }
}
