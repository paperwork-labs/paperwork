"use client";

import { cn } from "@paperwork-labs/ui";

import { STATUS_CLASSES, type StatusLevel } from "@/styles/design-tokens";

const SIZE_MAP = {
  sm: "h-1.5 w-1.5",
  md: "h-2 w-2",
  lg: "h-2.5 w-2.5",
} as const;

export type StatusDotProps = {
  status: StatusLevel;
  size?: keyof typeof SIZE_MAP;
  pulse?: boolean;
  className?: string;
};

export function StatusDot({ status, size = "md", pulse = false, className }: StatusDotProps) {
  const sizeCls = SIZE_MAP[size];
  const dotCls = STATUS_CLASSES[status].dot;

  if (!pulse) {
    return (
      <span className={cn("inline-block shrink-0 rounded-full", sizeCls, dotCls, className)} aria-hidden />
    );
  }

  return (
    <span className={cn("relative inline-block shrink-0", sizeCls)} aria-hidden>
      <span
        className={cn(
          "absolute inset-0 motion-safe:animate-ping rounded-full opacity-50",
          dotCls,
        )}
      />
      <span className={cn("relative inline-block shrink-0 rounded-full", sizeCls, dotCls, className)} />
    </span>
  );
}
