"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

const ActiveTabContext = React.createContext<string | null>(null);

/** Active tab id from ``TabbedPageShellNext`` (for optional child hooks). */
export function useActiveTab<T extends string>(): T {
  const v = React.useContext(ActiveTabContext);
  if (v == null) {
    throw new Error("useActiveTab must be used within TabbedPageShellNext");
  }
  return v as T;
}

export type TabbedShellTabDefNext<T extends string> = {
  id: T;
  label: string;
  Content: React.LazyExoticComponent<React.ComponentType>;
};

export type TabbedPageShellNextProps<T extends string> = {
  tabs: readonly TabbedShellTabDefNext<T>[];
  defaultTab: T;
  paramKey?: string;
  basePath: string;
  className?: string;
};

/**
 * Next.js App Router tab shell: syncs active tab to `?tab=` on *basePath* (AxiomFolio-style),
 * lazy-loads each tab module inside Suspense.
 */
export function TabbedPageShellNext<T extends string>({
  tabs,
  defaultTab,
  paramKey = "tab",
  basePath,
  className,
}: TabbedPageShellNextProps<T>) {
  const searchParams = useSearchParams();
  const allowed = React.useMemo(() => new Set(tabs.map((t) => t.id)), [tabs]);

  const raw = searchParams.get(paramKey) ?? "";
  const resolved: T = (allowed.has(raw as T) ? raw : defaultTab) as T;

  const activeDef = tabs.find((t) => t.id === resolved);
  const ActiveContent = activeDef?.Content;

  return (
    <ActiveTabContext.Provider value={resolved}>
      <div className={className}>
        <nav
          className="mb-4 inline-flex flex-wrap gap-1 rounded-lg border border-zinc-800 bg-zinc-900/60 p-1 text-sm"
          aria-label="Self-improvement sections"
        >
          {tabs.map((t) => {
            const active = t.id === resolved;
            const href = `${basePath}?${paramKey}=${encodeURIComponent(t.id)}`;
            return (
              <Link
                key={t.id}
                href={href}
                scroll={false}
                className={`rounded-md px-3 py-1.5 transition ${
                  active ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
        {ActiveContent ? (
          <React.Suspense
            fallback={
              <div
                className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400"
                aria-busy="true"
              >
                Loading tab…
              </div>
            }
          >
            <ActiveContent />
          </React.Suspense>
        ) : null}
      </div>
    </ActiveTabContext.Provider>
  );
}
