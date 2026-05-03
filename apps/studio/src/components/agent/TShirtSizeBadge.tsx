"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@paperwork-labs/ui";

export type TShirtSize = "XS" | "S" | "M" | "L" | "XL";

const SIZE_CONFIG: Record<
  TShirtSize,
  {
    model: string;
    colorClass: string;
    bgClass: string;
    borderClass: string;
    forbidden?: boolean;
  }
> = {
  XS: {
    model: "composer-1.5",
    colorClass: "text-emerald-300",
    bgClass: "bg-emerald-500/15",
    borderClass: "border-emerald-500/30",
  },
  S: {
    model: "composer-2-fast",
    colorClass: "text-green-300",
    bgClass: "bg-green-500/15",
    borderClass: "border-green-500/30",
  },
  M: {
    model: "gpt-5.5-medium",
    colorClass: "text-amber-300",
    bgClass: "bg-amber-500/15",
    borderClass: "border-amber-500/30",
  },
  L: {
    model: "claude-4.6-sonnet-medium-thinking",
    colorClass: "text-orange-300",
    bgClass: "bg-orange-500/15",
    borderClass: "border-orange-500/30",
  },
  XL: {
    model: "Opus (any)",
    colorClass: "text-red-300",
    bgClass: "bg-red-500/15",
    borderClass: "border-red-500/30",
    forbidden: true,
  },
};

interface TShirtSizeBadgeProps {
  size: TShirtSize;
  cost_cents?: number;
  className?: string;
}

function formatCost(cents: number): string {
  if (cents < 100) {
    const c = cents % 100;
    return `$0.${String(c).padStart(2, "0")}`;
  }
  return `$${(cents / 100).toFixed(2)}`;
}

export function TShirtSizeBadge({
  size,
  cost_cents,
  className = "",
}: TShirtSizeBadgeProps) {
  const cfg = SIZE_CONFIG[size] ?? SIZE_CONFIG.M;

  const badge = (
    <span
      className={`inline-flex cursor-default items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[11px] font-semibold ${cfg.colorClass} ${cfg.bgClass} ${cfg.borderClass} ${className}`}
    >
      {size}
      {cost_cents !== undefined && (
        <span className="ml-0.5 font-normal text-zinc-400">
          {formatCost(cost_cents)}
        </span>
      )}
    </span>
  );

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent className="max-w-[220px] text-xs">
          <p className="font-semibold">
            {size} — {cfg.model}
          </p>
          {cfg.forbidden && (
            <p className="mt-1 text-red-400">FORBIDDEN as subagent (orchestrator-only)</p>
          )}
          {cost_cents !== undefined && (
            <p className="mt-1 text-zinc-400">Est. cost: {formatCost(cost_cents)}</p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
