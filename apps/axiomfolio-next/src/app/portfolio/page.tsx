import { Wallet } from "lucide-react";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <Wallet className="h-5 w-5 text-sky-300" />
        <h1 className="text-xl font-semibold text-zinc-100">Portfolio</h1>
        <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-300">
          gold-read
        </span>
      </header>
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <h2 className="text-sm font-semibold text-zinc-100">Positions + workspace</h2>
        <p className="mt-2 text-xs text-zinc-500">
          Next PR ports{" "}
          <code className="rounded bg-zinc-950 px-1 text-zinc-300">
            PortfolioWorkspace.tsx
          </code>
          ,{" "}
          <code className="rounded bg-zinc-950 px-1 text-zinc-300">
            PortfolioImport.tsx
          </code>
          , and{" "}
          <code className="rounded bg-zinc-950 px-1 text-zinc-300">
            HoldingDetail.tsx
          </code>{" "}
          behind server components + streaming boundaries. The Vite route stays
          authoritative until the feature flag enables this tree.
        </p>
      </section>
    </div>
  );
}
