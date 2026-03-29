"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Trinkets unhandled error:", error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
      <div className="mx-auto max-w-md text-center">
        <p className="text-5xl font-bold tracking-tight text-destructive">
          Oops
        </p>
        <h1 className="mt-4 text-2xl font-bold tracking-tight">
          Something went wrong
        </h1>
        <p className="mt-2 text-muted-foreground">
          We&apos;ve been notified and are looking into it. Try again or head
          back to the homepage.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="rounded-lg bg-amber-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-amber-500"
          >
            Try again
          </button>
          <a
            href="/"
            className="rounded-lg border border-border px-6 py-2.5 text-sm font-medium text-foreground transition hover:bg-card"
          >
            Go home
          </a>
        </div>
      </div>
    </main>
  );
}
