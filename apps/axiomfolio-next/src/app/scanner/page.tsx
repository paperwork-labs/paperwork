import { Radar } from "lucide-react";

export default function ScannerPage() {
  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <Radar className="h-5 w-5 text-amber-300" />
        <h1 className="text-xl font-semibold text-zinc-100">Scanner</h1>
        <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
          gold-read
        </span>
      </header>
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <h2 className="text-sm font-semibold text-zinc-100">
          Stage + IV-rank scan
        </h2>
        <p className="mt-2 text-xs text-zinc-500">
          Next port brings the Weinstein stage scan, IV-rank surface, and the
          narrative tile from{" "}
          <code className="rounded bg-zinc-950 px-1 text-zinc-300">
            Scanner.tsx
          </code>{" "}
          to server components. Candles come from the existing
          <code className="rounded bg-zinc-950 px-1 text-zinc-300">
            /api/v1/signals
          </code>{" "}
          endpoint, so no backend changes required.
        </p>
      </section>
    </div>
  );
}
