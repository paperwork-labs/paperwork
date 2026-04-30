"use client";

import { useState, type ReactNode } from "react";

export type HqErrorStateProps = {
  title?: string;
  description?: string;
  error?: Error | string;
  onRetry?: () => void;
  icon?: ReactNode;
};

function formatError(error: Error | string | undefined) {
  if (!error) return "";
  if (typeof error === "string") return error;
  return error.stack ?? error.message;
}

/** Recoverable / admin error — distinct from empty and missing credentials. */
export function HqErrorState({
  title = "Something went wrong",
  description,
  error,
  onRetry,
  icon,
}: HqErrorStateProps) {
  const [open, setOpen] = useState(false);
  const detail = formatError(error);

  return (
    <div
      data-testid="hq-error-state"
      className="rounded-xl border border-red-500/40 bg-red-950/30 px-5 py-4"
    >
      <div className="flex flex-wrap items-start gap-3">
        {icon ? <div className="text-[rgb(252,165,165)]">{icon}</div> : null}
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-semibold text-[rgb(254,202,202)]">{title}</p>
          {description ? <p className="text-sm text-[rgb(254,215,215)]/90">{description}</p> : null}
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-md border border-[rgb(248,113,113)]/50 bg-black/20 px-3 py-1.5 text-sm font-medium text-[rgb(254,226,226)] transition hover:bg-black/30"
            >
              Retry
            </button>
          ) : null}
          {detail ? (
            <div className="pt-1">
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="text-xs font-medium text-[rgb(252,165,165)] underline-offset-2 hover:underline"
                aria-expanded={open}
              >
                {open ? "Hide details" : "Show details"}
              </button>
              {open ? (
                <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-black/40 p-3 text-left text-[11px] leading-snug text-zinc-300">
                  {detail}
                </pre>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
