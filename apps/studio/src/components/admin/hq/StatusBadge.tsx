"use client";

import type { ReactNode } from "react";

import { cn } from "@paperwork-labs/ui";

import { STATUS_CLASSES, type StatusLevel } from "@/styles/design-tokens";

export type StatusBadgeProps = {
  status: StatusLevel;
  children: ReactNode;
  size?: "sm" | "md";
  className?: string;
};

export function StatusBadge({ status, children, size = "md", className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border capitalize shadow-sm",
        STATUS_CLASSES[status].badge,
        size === "sm"
          ? "px-1.5 py-0 text-[10px] font-medium tracking-tight"
          : "px-2 py-0.5 text-xs font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}
