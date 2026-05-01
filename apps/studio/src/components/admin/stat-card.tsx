import Link from "next/link";
import { cn } from "@paperwork-labs/ui";
import type { ReactNode } from "react";

type StatCardProps = {
  label: string;
  value: ReactNode;
  delta?: { value: string; trend: "up" | "down" | "neutral" };
  href?: string;
  hint?: string;
  className?: string;
};

const trendClass = {
  up: "text-emerald-400",
  down: "text-rose-400",
  neutral: "text-zinc-500",
};

function isExternalHref(href: string) {
  return (
    href.startsWith("http://") || href.startsWith("https://") || href.startsWith("//")
  );
}

export function StatCard({ label, value, delta, href, hint, className }: StatCardProps) {
  const inner = (
    <>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">{value}</p>
      {delta ? (
        <p className={cn("mt-1 text-xs", trendClass[delta.trend])}>
          {delta.trend === "up" ? "↑" : delta.trend === "down" ? "↓" : "→"} {delta.value}
        </p>
      ) : null}
      {hint ? <p className="mt-2 text-xs text-zinc-500">{hint}</p> : null}
    </>
  );

  const baseClass =
    "rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 ring-1 ring-zinc-800/60 h-full";

  const interactiveShell =
    "block transition-colors hover:bg-zinc-900/60 hover:border-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/45";

  if (href) {
    if (isExternalHref(href)) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className={cn(baseClass, interactiveShell, className)}
        >
          {inner}
        </a>
      );
    }
    return (
      <Link href={href} className={cn(baseClass, interactiveShell, className)}>
        {inner}
      </Link>
    );
  }
  return <div className={cn(baseClass, className)}>{inner}</div>;
}
