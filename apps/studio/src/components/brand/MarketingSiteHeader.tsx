"use client";

import { SessionClippedWordmark } from "./SessionClippedWordmark";

export function MarketingSiteHeader() {
  return (
    <header className="border-b border-border/40">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-6">
        <SessionClippedWordmark surface="dark" className="max-w-[min(100%,360px)]" />
        <a
          href="mailto:hello@paperworklabs.com"
          className="shrink-0 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          hello@paperworklabs.com
        </a>
      </div>
    </header>
  );
}
