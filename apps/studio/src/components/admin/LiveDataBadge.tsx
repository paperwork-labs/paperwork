"use client";

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

type Props = {
  fetchedAtIso: string;
  className?: string;
};

/**
 * Header chip: “live as of HH:MM:SS” for Brain / cache refresh alignment.
 */
export function LiveDataBadge({ fetchedAtIso, className = "" }: Props) {
  return (
    <span
      className={`inline-flex items-center rounded-full border border-emerald-800/50 bg-emerald-950/30 px-2.5 py-1 font-mono text-[10px] text-emerald-300/90 ${className}`}
      title={`Server data timestamp: ${fetchedAtIso}`}
    >
      live as of {formatTime(fetchedAtIso)}
    </span>
  );
}
