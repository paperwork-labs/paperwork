import type { WorkstreamOwner, WorkstreamStatus } from "@/lib/workstreams/schema";

export function formatRelativeActivity(iso: string): string {
  const date = new Date(iso).getTime();
  const delta = date - Date.now();
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const abs = Math.abs(delta);
  const sec = Math.round(delta / 1000);
  const min = Math.round(delta / 60_000);
  const hour = Math.round(delta / 3_600_000);
  const day = Math.round(delta / 86_400_000);
  if (abs < 60_000) return rtf.format(sec, "second");
  if (abs < 3_600_000) return rtf.format(min, "minute");
  if (abs < 86_400_000) return rtf.format(hour, "hour");
  if (abs < 604_800_000) return rtf.format(day, "day");
  const week = Math.round(delta / 604_800_000);
  if (abs < 2_629_800_000) return rtf.format(week, "week");
  const month = Math.round(delta / 2_629_800_000);
  if (abs < 31_557_600_000) return rtf.format(month, "month");
  return rtf.format(Math.round(delta / 31_557_600_000), "year");
}

export function statusPillClass(status: WorkstreamStatus): string {
  switch (status) {
    case "pending":
      return "border-zinc-600 bg-zinc-900/90 text-zinc-300";
    case "in_progress":
      return "border-sky-700/70 bg-sky-950/50 text-sky-200";
    case "blocked":
      return "border-amber-700/70 bg-amber-950/45 text-amber-200";
    case "completed":
      return "border-emerald-700/70 bg-emerald-950/45 text-emerald-200";
    case "cancelled":
      return "border-rose-800/60 bg-rose-950/40 text-rose-200";
    default:
      return "border-zinc-600 bg-zinc-900 text-zinc-300";
  }
}

export function ownerBadgeClass(owner: WorkstreamOwner): string {
  switch (owner) {
    case "brain":
      return "bg-violet-500/15 text-violet-200 ring-violet-500/25";
    case "founder":
      return "bg-amber-500/15 text-amber-200 ring-amber-500/25";
    case "opus":
      return "bg-cyan-500/15 text-cyan-200 ring-cyan-500/25";
    default:
      return "bg-zinc-800 text-zinc-300 ring-zinc-600/40";
  }
}
