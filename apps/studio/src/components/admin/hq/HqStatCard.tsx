"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

export type HqStatCardStatus =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info";

export type HqStatCardProps = {
  label: string;
  value: string | number;
  delta?: { direction: "up" | "down" | "flat"; value: string };
  helpText?: string;
  variant?: "compact" | "default";
  status?: HqStatCardStatus;
  /** Optional leading icon inside the label row */
  icon?: ReactNode;
};

/**
 * Inline semantic emphasis (card chrome). Count-up and delta read global
 * `--status-*` from `src/styles/tokens.css`.
 */
const STATUS_TOKEN_STYLE: Record<HqStatCardStatus, CSSProperties> = {
  neutral: {
    ["--status-neutral" as string]: "1",
    ["--status-success" as string]: "0",
    ["--status-warning" as string]: "0",
    ["--status-danger" as string]: "0",
    ["--status-info" as string]: "0",
    borderColor: "rgb(63 63 70 / 0.55)",
    backgroundColor: "rgb(9 9 11 / 0.45)",
    color: "rgb(244 244 245)",
  },
  success: {
    ["--status-neutral" as string]: "0",
    ["--status-success" as string]: "1",
    ["--status-warning" as string]: "0",
    ["--status-danger" as string]: "0",
    ["--status-info" as string]: "0",
    borderColor: "rgb(22 163 74 / 0.4)",
    backgroundColor: "rgb(20 83 45 / 0.2)",
    color: "rgb(187 247 208)",
  },
  warning: {
    ["--status-neutral" as string]: "0",
    ["--status-success" as string]: "0",
    ["--status-warning" as string]: "1",
    ["--status-danger" as string]: "0",
    ["--status-info" as string]: "0",
    borderColor: "rgb(217 119 6 / 0.45)",
    backgroundColor: "rgb(120 53 15 / 0.22)",
    color: "rgb(254 243 199)",
  },
  danger: {
    ["--status-neutral" as string]: "0",
    ["--status-success" as string]: "0",
    ["--status-warning" as string]: "0",
    ["--status-danger" as string]: "1",
    ["--status-info" as string]: "0",
    borderColor: "rgb(220 38 38 / 0.45)",
    backgroundColor: "rgb(127 29 29 / 0.22)",
    color: "rgb(254 202 202)",
  },
  info: {
    ["--status-neutral" as string]: "0",
    ["--status-success" as string]: "0",
    ["--status-warning" as string]: "0",
    ["--status-danger" as string]: "0",
    ["--status-info" as string]: "1",
    borderColor: "rgb(2 132 199 / 0.45)",
    backgroundColor: "rgb(12 74 110 / 0.22)",
    color: "rgb(224 242 254)",
  },
};

function easeOutCubic(t: number) {
  return 1 - (1 - t) ** 3;
}

function fractionalDigits(n: number): number {
  if (!Number.isFinite(n)) return 0;
  const s = n.toString();
  const dot = s.indexOf(".");
  return dot === -1 ? 0 : s.length - dot - 1;
}

function formatAnimatedValue(raw: number, target: number): number | string {
  const d = fractionalDigits(target);
  if (d > 0) return Number(raw.toFixed(d));
  return Math.round(raw);
}

function deltaClass(direction: "up" | "down" | "flat") {
  if (direction === "up") return "text-[var(--status-success)]";
  if (direction === "down") return "text-[var(--status-danger)]";
  return "text-[var(--status-muted)]";
}

/** KPI / stat tile for HQ dashboards — compact (6-up) or default (4-up) density. */
export function HqStatCard({
  label,
  value,
  delta,
  helpText,
  variant = "default",
  status = "neutral",
  icon,
}: HqStatCardProps) {
  const tokenStyle = STATUS_TOKEN_STYLE[status];
  const pad = variant === "compact" ? "px-3 py-2.5" : "px-4 py-4";
  const valueSize = variant === "compact" ? "text-xl" : "text-2xl";

  const firstAnimDone = useRef(false);
  const [displayValue, setDisplayValue] = useState<string | number>(() => {
    if (typeof value === "number" && Number.isFinite(value)) {
      if (
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        return value;
      }
      return 0;
    }
    return value;
  });

  useEffect(() => {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      setDisplayValue(value);
      return;
    }

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setDisplayValue(value);
      firstAnimDone.current = true;
      return;
    }

    if (firstAnimDone.current) {
      setDisplayValue(value);
      return;
    }

    const durationMs = 600;
    const target = value;
    let startWall: number | null = null;
    let rafId = 0;

    const frame = (now: number) => {
      if (startWall === null) startWall = now;
      const t = Math.min(1, (now - startWall) / durationMs);
      const eased = easeOutCubic(t);
      const current = eased * target;
      setDisplayValue(formatAnimatedValue(current, target));
      if (t < 1) {
        rafId = requestAnimationFrame(frame);
      } else {
        setDisplayValue(target);
        firstAnimDone.current = true;
      }
    };

    rafId = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafId);
  }, [value]);

  return (
    <div
      data-testid="hq-stat-card"
      data-hq-stat-status={status}
      className={`rounded-xl border ring-1 ring-inset ring-black/5 ${pad}`}
      style={tokenStyle}
    >
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">{label}</p>
      </div>
      <p
        data-testid="hq-stat-value"
        className={`mt-1 font-semibold tabular-nums ${valueSize}`}
      >
        {displayValue}
      </p>
      {delta ? (
        <p className={`mt-0.5 text-xs font-medium ${deltaClass(delta.direction)}`}>{delta.value}</p>
      ) : null}
      {helpText ? <p className="mt-1 text-xs text-zinc-500">{helpText}</p> : null}
    </div>
  );
}
