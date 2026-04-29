"use client";

import * as React from "react";

import { cn } from "../lib/utils";

export type FilterChip = { id: string; label: string; count?: number };

export type FilterChipRowProps = {
  chips: FilterChip[];
  value: string;
  onChange: (id: string) => void;
  variant?: "outline" | "solid";
  endAdornment?: React.ReactNode;
  className?: string;
};

export function FilterChipRow({
  chips,
  value,
  onChange,
  variant = "outline",
  endAdornment,
  className,
}: FilterChipRowProps) {
  if (chips.length === 0) {
    return (
      <div
        className={cn("flex min-h-10 items-center text-sm text-muted-foreground", className)}
        role="status"
        aria-live="polite"
      >
        No filters available
      </div>
    );
  }

  return (
    <div
      className={cn("flex min-w-0 items-center gap-2", className)}
      role="toolbar"
      aria-label="Filter chips"
    >
      <div className="flex min-w-0 flex-1 gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {chips.map((chip) => {
          const active = chip.id === value;
          return (
            <button
              key={chip.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(chip.id)}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
                variant === "outline" &&
                  (active
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-background text-muted-foreground hover:bg-muted/60 hover:text-foreground"),
                variant === "solid" &&
                  (active
                    ? "border-transparent bg-primary text-primary-foreground"
                    : "border-transparent bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"),
              )}
            >
              <span>{chip.label}</span>
              {chip.count != null ? (
                <span
                  className={cn(
                    "rounded-full px-1.5 py-0.5 text-xs tabular-nums",
                    active ? "bg-background/20 text-inherit" : "bg-background/80 text-foreground",
                  )}
                >
                  {chip.count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      {endAdornment ? <div className="shrink-0">{endAdornment}</div> : null}
    </div>
  );
}
