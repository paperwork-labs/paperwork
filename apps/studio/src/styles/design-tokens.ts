/**
 * Studio admin status semantics — mirrors `--status-*` in `src/styles/tokens.css`
 * (loaded via `globals.css`).
 */
export const STATUS_COLORS = {
  success: "var(--status-success)",
  successBg: "var(--status-success-bg)",
  warning: "var(--status-warning)",
  warningBg: "var(--status-warning-bg)",
  danger: "var(--status-danger)",
  dangerBg: "var(--status-danger-bg)",
  info: "var(--status-info)",
  infoBg: "var(--status-info-bg)",
  muted: "var(--status-muted)",
} as const;

export const STATUS_CLASSES = {
  success: {
    dot: "bg-[var(--status-success)]",
    badge:
      "border-[var(--status-success)]/50 bg-[var(--status-success-bg)] text-[var(--status-success)]",
    ring: "ring-[var(--status-success)]/40",
  },
  warning: {
    dot: "bg-[var(--status-warning)]",
    badge:
      "border-[var(--status-warning)]/50 bg-[var(--status-warning-bg)] text-[var(--status-warning)]",
    ring: "ring-[var(--status-warning)]/40",
  },
  danger: {
    dot: "bg-[var(--status-danger)]",
    badge:
      "border-[var(--status-danger)]/50 bg-[var(--status-danger-bg)] text-[var(--status-danger)]",
    ring: "ring-[var(--status-danger)]/40",
  },
  info: {
    dot: "bg-[var(--status-info)]",
    badge:
      "border-[var(--status-info)]/50 bg-[rgb(12_74_110/0.22)] text-[rgb(224_242_254)]",
    ring: "ring-[var(--status-info)]/40",
  },
  neutral: {
    dot: "bg-zinc-500",
    badge: "border-zinc-600 bg-zinc-800/70 text-zinc-300",
    ring: "ring-zinc-400/30",
  },
} as const;

export type StatusLevel = keyof typeof STATUS_CLASSES;
