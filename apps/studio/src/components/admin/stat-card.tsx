"use client";

import Link from "next/link";
import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@paperwork-labs/ui";

export type StatCardProps = {
  label: string;
  value: ReactNode;
  delta?: { value: string; trend: "up" | "down" | "neutral" };
  href?: string;
  hint?: string;
  className?: string;
  icon?: ReactNode;
  compact?: boolean;
  selected?: boolean;
  ariaLabel?: string;
  external?: boolean;
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

function deltaClass(trend: "up" | "down" | "neutral") {
  if (trend === "up") return "text-sky-300";
  if (trend === "down") return "text-zinc-400";
  return "text-zinc-500";
}

function useAnimatedNumber(target: number | null): number | null {
  const firstAnimDone = useRef(false);
  const [display, setDisplay] = useState<number | null>(() => {
    if (target === null) return null;
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return target;
    }
    return 0;
  });

  useEffect(() => {
    if (target === null) {
      setDisplay(null);
      return;
    }

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setDisplay(target);
      firstAnimDone.current = true;
      return;
    }

    if (firstAnimDone.current) {
      setDisplay(target);
      return;
    }

    const durationMs = 600;
    let startWall: number | null = null;
    let rafId = 0;

    const frame = (now: number) => {
      if (startWall === null) startWall = now;
      const t = Math.min(1, (now - startWall) / durationMs);
      const eased = easeOutCubic(t);
      const current = eased * target;
      setDisplay(formatAnimatedValue(current, target));
      if (t < 1) {
        rafId = requestAnimationFrame(frame);
      } else {
        setDisplay(target);
        firstAnimDone.current = true;
      }
    };

    rafId = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafId);
  }, [target]);

  return display;
}

function StatCardValueSlot({
  value,
  compact,
}: {
  value: ReactNode;
  compact?: boolean;
}) {
  const numeric =
    typeof value === "number" && Number.isFinite(value) ? value : null;
  const animated = useAnimatedNumber(numeric);
  const body = numeric !== null ? animated : value;

  return (
    <p
      data-testid="hq-stat-value"
      className={cn(
        "mt-1 tabular-nums font-semibold text-zinc-100",
        compact ? "text-xl" : "text-2xl",
      )}
    >
      {body}
    </p>
  );
}

export function StatCard({
  label,
  value,
  delta,
  href,
  hint,
  className,
  icon,
  compact = false,
  selected = false,
  ariaLabel,
  external,
}: StatCardProps) {
  const isExternal =
    external === true ||
    (href?.startsWith("http://") ?? false) ||
    (href?.startsWith("https://") ?? false);

  const shell = cn(
    "block rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 text-left outline-none transition-colors duration-200 ease-out",
    href && "motion-safe:hover:bg-zinc-900/60",
    selected &&
      "ring-2 ring-sky-500/35 ring-offset-2 ring-offset-zinc-950",
    href &&
      "cursor-pointer focus-visible:ring-2 focus-visible:ring-sky-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
    className,
  );

  const inner = (
    <>
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-[11px] font-medium uppercase tracking-widest text-zinc-500">
          {label}
        </p>
      </div>
      <StatCardValueSlot value={value} compact={compact} />
      {delta ? (
        <p
          className={cn(
            "mt-0.5 text-xs font-medium",
            deltaClass(delta.trend),
          )}
        >
          {delta.value}
        </p>
      ) : null}
      {hint ? (
        <p className="mt-2 text-xs text-zinc-500">{hint}</p>
      ) : null}
    </>
  );

  if (href) {
    const a11y = ariaLabel ? { "aria-label": ariaLabel } : {};
    if (isExternal) {
      return (
        <a
          data-testid="hq-stat-card"
          href={href}
          className={shell}
          target="_blank"
          rel="noreferrer"
          {...a11y}
        >
          {inner}
        </a>
      );
    }
    return (
      <Link
        data-testid="hq-stat-card"
        href={href}
        className={shell}
        prefetch={false}
        {...a11y}
      >
        {inner}
      </Link>
    );
  }

  return (
    <div data-testid="hq-stat-card" className={shell}>
      {inner}
    </div>
  );
}
