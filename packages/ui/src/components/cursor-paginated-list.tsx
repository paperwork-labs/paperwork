"use client";

import * as React from "react";

import { cn } from "../lib/utils";

export type CursorPaginatedListProps<T> = {
  fetchPage: (cursor: string | null) => Promise<{ items: T[]; nextCursor: string | null }>;
  renderItem: (item: T) => React.ReactNode;
  keyFor: (item: T) => string;
  autoRefreshMs?: number;
  emptyState?: React.ReactNode;
  errorState?: (err: Error, retry: () => void) => React.ReactNode;
  loadingSkeleton?: React.ReactNode;
};

const DEFAULT_SKELETON = (
  <div className="flex flex-col gap-2 py-4" aria-busy="true" aria-label="Loading list">
    {Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />
    ))}
  </div>
);

function DefaultErrorState({ err, retry }: { err: Error; retry: () => void }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm" role="alert">
      <p className="font-medium text-destructive">Could not load items</p>
      <p className="mt-1 text-muted-foreground">{err.message}</p>
      <button
        type="button"
        className="mt-3 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted"
        onClick={retry}
      >
        Retry
      </button>
    </div>
  );
}

export function CursorPaginatedList<T>({
  fetchPage,
  renderItem,
  keyFor,
  autoRefreshMs,
  emptyState,
  errorState,
  loadingSkeleton,
}: CursorPaginatedListProps<T>) {
  const [items, setItems] = React.useState<T[]>([]);
  const [nextCursor, setNextCursor] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [loadingMore, setLoadingMore] = React.useState(false);
  const [error, setError] = React.useState<Error | null>(null);
  const sentinelRef = React.useRef<HTMLDivElement | null>(null);
  const inFlight = React.useRef(false);
  const listVersion = React.useRef(0);

  const loadInitial = React.useCallback(async () => {
    const v = ++listVersion.current;
    setLoading(true);
    setError(null);
    try {
      const page = await fetchPage(null);
      if (v !== listVersion.current) return;
      setItems(page.items);
      setNextCursor(page.nextCursor);
    } catch (e) {
      if (v !== listVersion.current) return;
      setError(e instanceof Error ? e : new Error(String(e)));
      setItems([]);
      setNextCursor(null);
    } finally {
      if (v === listVersion.current) setLoading(false);
    }
  }, [fetchPage]);

  const loadMore = React.useCallback(async () => {
    if (nextCursor == null || inFlight.current || document.visibilityState === "hidden") return;
    const v = listVersion.current;
    inFlight.current = true;
    setLoadingMore(true);
    setError(null);
    try {
      const page = await fetchPage(nextCursor);
      if (v !== listVersion.current) return;
      setItems((prev) => [...prev, ...page.items]);
      setNextCursor(page.nextCursor);
    } catch (e) {
      if (v !== listVersion.current) return;
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      inFlight.current = false;
      setLoadingMore(false);
    }
  }, [fetchPage, nextCursor]);

  React.useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  React.useEffect(() => {
    if (autoRefreshMs == null || autoRefreshMs <= 0) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "hidden") return;
      void loadInitial();
    }, autoRefreshMs);
    return () => window.clearInterval(id);
  }, [autoRefreshMs, loadInitial]);

  React.useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        const hit = entries.some((e) => e.isIntersecting);
        if (hit && document.visibilityState === "visible") void loadMore();
      },
      { root: null, rootMargin: "80px", threshold: 0 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadMore, items.length, nextCursor]);

  if (loading && items.length === 0) {
    return <>{loadingSkeleton ?? DEFAULT_SKELETON}</>;
  }

  if (error && items.length === 0) {
    const err = error;
    const retry = () => void loadInitial();
    return <>{errorState ? errorState(err, retry) : <DefaultErrorState err={err} retry={retry} />}</>;
  }

  if (!loading && items.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground" role="status">
        {emptyState ?? "Nothing to show yet."}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2" aria-busy={loadingMore}>
        {items.map((item) => (
          <li key={keyFor(item)}>{renderItem(item)}</li>
        ))}
      </ul>
      {error && items.length > 0 ? (
        <div className="text-sm text-destructive" role="alert">
          {error.message}{" "}
          <button type="button" className="underline" onClick={() => void loadMore()}>
            Try loading more
          </button>
        </div>
      ) : null}
      <div ref={sentinelRef} className={cn("h-1 w-full", nextCursor == null && "hidden")} aria-hidden />
      {loadingMore ? (
        <div className="text-center text-xs text-muted-foreground" aria-live="polite">
          Loading more…
        </div>
      ) : null}
    </div>
  );
}
