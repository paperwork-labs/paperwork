import { Activity, CheckCircle2, CircleAlert } from "lucide-react";

type LayerTile = {
  id: "bronze" | "silver" | "gold" | "execution";
  label: string;
  description: string;
  count: number;
  healthy: boolean;
};

async function loadLayers(): Promise<LayerTile[]> {
  // TODO(track-e-phase-2): call the axiomfolio system-status API over fetch
  // and return live tiles. For now, render the deterministic baseline so
  // the shell is visually complete and the layout can be reviewed without
  // backend coupling.
  return [
    {
      id: "bronze",
      label: "Bronze",
      description: "Raw broker I/O, ingestion pipelines, external adapters.",
      count: 38,
      healthy: true,
    },
    {
      id: "silver",
      label: "Silver",
      description: "Enrichment, analytics, reconciliation, data quality.",
      count: 80,
      healthy: true,
    },
    {
      id: "gold",
      label: "Gold",
      description: "Strategy outputs, picks, backtests, narratives.",
      count: 56,
      healthy: true,
    },
    {
      id: "execution",
      label: "Execution",
      description: "Reads gold, writes orders to brokers. Append-only ledgers.",
      count: 22,
      healthy: true,
    },
  ];
}

export default async function SystemStatusPage() {
  const layers = await loadLayers();
  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <Activity className="h-5 w-5 text-emerald-300" />
        <h1 className="text-xl font-semibold text-zinc-100">System Status</h1>
        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
          medallion
        </span>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {layers.map((layer) => (
          <section
            key={layer.id}
            className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-zinc-100">{layer.label}</h2>
              {layer.healthy ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <CircleAlert className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <p className="mt-2 text-xs text-zinc-400">{layer.description}</p>
            <p className="mt-4 text-2xl font-semibold text-zinc-100">
              {layer.count.toLocaleString()}
              <span className="ml-2 text-[10px] uppercase tracking-wide text-zinc-500">
                services
              </span>
            </p>
          </section>
        ))}
      </div>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <h2 className="text-sm font-semibold text-zinc-100">Live probes</h2>
        <p className="mt-2 text-xs text-zinc-500">
          Full port from the Vite system-status page lands in the next PR. The
          backend health API already exposes everything this view needs; this
          shell just scaffolds the Next.js route so we can iterate without
          breaking the Vite deployment.
        </p>
      </section>
    </div>
  );
}
