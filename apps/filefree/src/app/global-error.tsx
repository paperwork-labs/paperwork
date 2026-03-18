"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <div className="mx-auto max-w-md px-4 text-center">
          <h2 className="text-2xl font-bold">Something went wrong</h2>
          <p className="mt-2 text-muted-foreground">
            We&apos;ve been notified and are looking into it.
          </p>
          <button
            onClick={reset}
            className="mt-6 rounded-lg bg-violet-600 px-6 py-2 text-sm font-medium text-white hover:bg-violet-500"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
