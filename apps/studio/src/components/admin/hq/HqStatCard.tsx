import type { CSSProperties, ReactNode } from "react";

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
 * Inline semantic tokens (Wave L PR-B → tokens.css). Each status exposes the
 * full `--status-*` set so future global CSS can key off any variable; the
 * active row sets opacity 1 on its matching token.
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

function deltaClass(direction: "up" | "down" | "flat") {
  if (direction === "up") return "text-[rgb(134,239,172)]";
  if (direction === "down") return "text-[rgb(252,165,165)]";
  return "text-zinc-500";
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
      <p className={`mt-1 font-semibold tabular-nums ${valueSize}`}>{value}</p>
      {delta ? (
        <p className={`mt-0.5 text-xs font-medium ${deltaClass(delta.direction)}`}>{delta.value}</p>
      ) : null}
      {helpText ? <p className="mt-1 text-xs text-zinc-500">{helpText}</p> : null}
    </div>
  );
}
