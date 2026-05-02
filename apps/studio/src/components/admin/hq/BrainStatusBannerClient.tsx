"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { useState } from "react";

export type BrainStatusBannerVariant = "down" | "degraded";

type Props = {
  variant: BrainStatusBannerVariant;
};

export function BrainStatusBannerClient({ variant }: Props) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const isDown = variant === "down";
  const bar = isDown
    ? "border-l-red-500 bg-red-500/10 text-red-200"
    : "border-l-amber-500 bg-amber-500/10 text-amber-200";

  const lead = isDown
    ? "Brain API unreachable — some data may be unavailable."
    : "Brain API responding slowly — some data may be unavailable.";

  return (
    <div
      role="alert"
      data-testid="brain-status-banner"
      data-variant={variant}
      className={`sticky top-0 z-[55] mb-4 flex min-h-9 items-center gap-3 border-b border-zinc-800/80 border-l-4 px-3 py-1.5 text-sm ${bar}`}
    >
      <span className="min-w-0 flex-1 leading-tight">
        <span aria-hidden>⚠ </span>
        {lead}{" "}
        <Link
          href="/admin/infrastructure?tab=services"
          className="font-medium underline decoration-zinc-400/80 underline-offset-2 hover:text-zinc-50"
        >
          Check status
        </Link>
        .
      </span>
      <button
        type="button"
        aria-label="Dismiss Brain status alert"
        data-testid="brain-status-banner-dismiss"
        className="shrink-0 rounded p-1 text-current opacity-80 motion-safe:transition-opacity hover:opacity-100"
        onClick={() => setDismissed(true)}
      >
        <X className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
