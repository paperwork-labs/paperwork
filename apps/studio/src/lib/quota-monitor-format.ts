/** UI thresholds (studio): quick scan alignment with product-risk bands. */

export const VERCEL_DEPLOY_DAILY_CAP = 100;
export const VERCEL_BUILD_30D_CAP = 6000;

export type ThresholdTone = "ok" | "warn" | "bad";

/** Green below 60%, amber 60–85%, red above 85%. */
export function thresholdToneFromPct(pct: number): ThresholdTone {
  if (!Number.isFinite(pct)) return "ok";
  if (pct < 60) return "ok";
  if (pct <= 85) return "warn";
  return "bad";
}

export function formatPercent1(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return `${Math.min(999, Math.max(0, n)).toFixed(1)}%`;
}

export function pctOf(used: number, cap: number): number | null {
  if (!Number.isFinite(used) || !Number.isFinite(cap) || cap <= 0) return null;
  return Math.min(100, Math.max(0, (used / cap) * 100));
}

export function toneAccentClass(tone: ThresholdTone): {
  bg: string;
  text: string;
  bar: string;
  dot: string;
} {
  switch (tone) {
    case "warn":
      return {
        bg: "bg-[var(--status-warning)]",
        text: "text-[var(--status-warning)]",
        bar: "bg-[var(--status-warning)]",
        dot: "bg-[var(--status-warning)]",
      };
    case "bad":
      return {
        bg: "bg-[var(--status-danger)]",
        text: "text-[var(--status-danger)]",
        bar: "bg-[var(--status-danger)]",
        dot: "bg-[var(--status-danger)]",
      };
    default:
      return {
        bg: "bg-[var(--status-success)]",
        text: "text-[var(--status-success)]",
        bar: "bg-[var(--status-success)]",
        dot: "bg-[var(--status-success)]",
      };
  }
}

/** Format fractional minutes as `Xh Ym` when ≥ 1h, else rounded minutes with `m` suffix. */
export function formatPipelineMinutes(totalMinutes: number): string {
  if (!Number.isFinite(totalMinutes)) return "—";
  const clamped = Math.max(0, totalMinutes);
  const h = Math.floor(clamped / 60);
  const m = Math.round(clamped % 60);
  if (h <= 0) return `${Math.round(clamped)}m`;
  return `${h}h ${m}m`;
}

export function formatBytesIEC(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes) || bytes < 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  const digits = i === 0 ? 0 : v >= 10 ? 1 : 2;
  return `${v.toFixed(digits)} ${units[i]}`;
}

/** True when Brain snapshot timestamp is older than `maxAgeMin` minutes. */
export function isStaleIso(iso: string | null | undefined, maxAgeMin = 25): boolean {
  if (!iso) return true;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return true;
  return Date.now() - t > maxAgeMin * 60 * 1000;
}
