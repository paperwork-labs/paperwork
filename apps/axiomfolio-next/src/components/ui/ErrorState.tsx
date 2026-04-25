/**
 * `ErrorState` — actionable error empty-state with optional retry.
 *
 * Mirrors the API of `EmptyState` so callers swap one for the other when
 * the four-state contract (loading / error / empty / data) flips. The
 * underlying error object is rendered in a collapsed `<details>` block
 * ONLY in development builds — production users never see stack traces
 * (no information disclosure to attackers).
 */
import * as React from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface ErrorStateProps {
  title: string;
  description?: string;
  /** Optional error object surfaced as a collapsed `<details>` in dev only. */
  error?: unknown;
  retry?: () => void;
  retryLabel?: string;
  icon?: React.ElementType;
  className?: string;
}

function formatError(err: unknown): string {
  if (err == null) return "";
  if (err instanceof Error) {
    return err.stack ?? `${err.name}: ${err.message}`;
  }
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err, null, 2);
  } catch {
    return String(err);
  }
}

export function ErrorState({
  title,
  description,
  error,
  retry,
  retryLabel = "Try again",
  icon: Icon = AlertTriangle,
  className,
}: ErrorStateProps) {
  const isDev = process.env.NODE_ENV === "development";
  const showDetails = isDev && error != null;
  const formatted = showDetails ? formatError(error) : "";

  return (
    <Card
      role="alert"
      className={cn(
        "border-0 bg-transparent py-0 shadow-none ring-0",
        className,
      )}
    >
      <CardContent className="px-0 py-12 text-center">
        <div className="flex flex-col items-center gap-3">
          <Icon className="size-10 text-destructive" aria-hidden />
          <h2 className="font-heading text-base font-medium text-foreground">
            {title}
          </h2>
          {description ? (
            <p className="max-w-3xl text-sm text-muted-foreground">
              {description}
            </p>
          ) : null}
          {retry ? (
            <Button type="button" variant="outline" onClick={retry}>
              {retryLabel}
            </Button>
          ) : null}
          {showDetails ? (
            <details className="mt-2 max-w-3xl text-left">
              <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                Show error details (dev only)
              </summary>
              <pre className="mt-2 overflow-auto rounded-md border border-border bg-muted/50 p-3 text-[11px] leading-snug text-foreground">
                {formatted}
              </pre>
            </details>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export default ErrorState;
