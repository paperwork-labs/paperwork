export type MoneyFormatOptions = {
  maximumFractionDigits?: number;
  minimumFractionDigits?: number;
  /** Use 'compact' for short forms like 1.2K, 3.5M */
  notation?: 'standard' | 'compact';
};

function safeDate(value: string | number | Date): Date | null {
  // Backend timestamps should be UTC. If we get an ISO-like string without a timezone,
  // normalize it to UTC by appending "Z" so the browser doesn't interpret it as local time.
  const normalized =
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(value) &&
    !/[zZ]$/.test(value)
      ? `${value}Z`
      : value;
  const d = normalized instanceof Date ? normalized : new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

function safeCurrency(code: string | undefined | null): string {
  const c = String(code || "USD").trim().toUpperCase();
  if (c.length !== 3) return "USD";
  return c;
}

export function formatMoney(
  amount: number | string | null | undefined,
  currency: string | undefined | null,
  opts: MoneyFormatOptions = {}
): string {
  const n = Number(amount ?? 0);
  const cur = safeCurrency(currency);
  const maximumFractionDigits = opts.maximumFractionDigits ?? 2;
  const minimumFractionDigits = opts.minimumFractionDigits ?? 0;
  const notation = opts.notation;
  const intlOpts: Intl.NumberFormatOptions = {
    style: "currency",
    currency: cur,
    maximumFractionDigits,
    minimumFractionDigits,
  };
  if (notation) intlOpts.notation = notation;
  try {
    return new Intl.NumberFormat("en-US", intlOpts).format(Number.isFinite(n) ? n : 0);
  } catch {
    // If currency code is invalid for this runtime, fall back to USD.
    return new Intl.NumberFormat("en-US", { ...intlOpts, currency: "USD" }).format(Number.isFinite(n) ? n : 0);
  }
}

export function formatDateTime(
  value: string | number | Date | null | undefined,
  timezone: string | undefined | null
): string {
  if (value == null) return "—";
  const d = safeDate(value);
  if (!d) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: timezone || undefined,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  }
}

export function formatDate(
  value: string | number | Date | null | undefined,
  timezone: string | undefined | null
): string {
  if (value == null) return "—";
  const d = safeDate(value);
  if (!d) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: timezone || undefined,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
  }
}

export function formatTime(
  value: string | number | Date | null | undefined,
  timezone: string | undefined | null
): string {
  if (value == null) return "—";
  const d = safeDate(value);
  if (!d) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: timezone || undefined,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(d);
  }
}

/**
 * Friendly date format: "Mar 25, 2026"
 */
export function formatDateFriendly(
  value: string | number | Date | null | undefined,
  timezone: string | undefined | null
): string {
  if (value == null) return "—";
  const d = safeDate(value);
  if (!d) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: timezone || undefined,
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(d);
  }
}

/**
 * Friendly date + time format: "Mar 25, 2026, 3:45 PM"
 */
export function formatDateTimeFriendly(
  value: string | number | Date | null | undefined,
  timezone: string | undefined | null
): string {
  if (value == null) return "—";
  const d = safeDate(value);
  if (!d) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: timezone || undefined,
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(d);
  }
}

/**
 * Short date format (no year): "Mar 25"
 */
export function formatDateShort(
  value: string | number | Date | null | undefined,
  timezone: string | undefined | null
): string {
  if (value == null) return "—";
  const d = safeDate(value);
  if (!d) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: timezone || undefined,
      month: "short",
      day: "numeric",
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
    }).format(d);
  }
}

/**
 * Relative time format: "just now", "5m ago", "2h ago", "3d ago"
 * Consolidated from multiple implementations across the codebase.
 */
export function formatRelativeTime(
  value: string | number | Date | null | undefined
): string {
  if (value == null) return "";
  const d = safeDate(value);
  if (!d) return "";
  const diff = Date.now() - d.getTime();
  if (diff < 0) return "just now";
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

/**
 * ISO date format for APIs/inputs: "2026-03-25"
 */
export function formatISODate(
  value: string | number | Date | null | undefined
): string {
  if (value == null) return "";
  const d = safeDate(value);
  if (!d) return "";
  return d.toISOString().slice(0, 10);
}

