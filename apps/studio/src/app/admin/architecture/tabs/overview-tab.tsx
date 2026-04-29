import { ExternalLink, GitBranch, Layers, BookOpen } from "lucide-react";
import { getArchitecturePayload } from "@/lib/get-architecture-payload";
import { systemGraph } from "@/lib/system-graph";
import ArchitectureClient from "../architecture-client";

export const dynamic = "force-dynamic";

const APPS = [
  {
    name: "Studio",
    path: "apps/studio",
    description:
      "Internal admin dashboard — the command centre for ops, Brain visibility, sprints, workstreams, and infrastructure health.",
    github: "https://github.com/paperwork-labs/paperwork/tree/main/apps/studio",
  },
  {
    name: "AxiomFolio",
    path: "apps/axiomfolio",
    description:
      "Customer-facing portfolio and wealth intelligence app — positions, performance, tax lots, and data-room features.",
    github: "https://github.com/paperwork-labs/paperwork/tree/main/apps/axiomfolio",
  },
  {
    name: "Brain API",
    path: "apis/brain",
    description:
      "FastAPI service powering AI personas, long-term memory, self-improvement loops, and the /ask endpoints consumed by Studio and AxiomFolio.",
    github: "https://github.com/paperwork-labs/paperwork/tree/main/apis/brain",
  },
  {
    name: "AxiomFolio API",
    path: "apis/axiomfolio",
    description:
      "Data-plane API for portfolio ingestion, position normalisation, pricing, and tax calculations. Feeds AxiomFolio's frontend.",
    github: "https://github.com/paperwork-labs/paperwork/tree/main/apis/axiomfolio",
  },
];

export default async function OverviewTab() {
  const { health, checkedAt, nodeLive, live_data } = await getArchitecturePayload();

  return (
    <div className="space-y-8">
      {/* Quick links */}
      <section className="flex flex-wrap gap-3">
        <a
          href="https://github.com/paperwork-labs/paperwork/blob/main/docs/ARCHITECTURE.md"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/60"
        >
          <BookOpen className="h-4 w-4 text-zinc-400" />
          Architecture docs
          <ExternalLink className="h-3 w-3 opacity-60" />
        </a>
        <a
          href="https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/60"
        >
          <Layers className="h-4 w-4 text-zinc-400" />
          Brain architecture
          <ExternalLink className="h-3 w-3 opacity-60" />
        </a>
        <a
          href="https://github.com/paperwork-labs/paperwork"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-700 hover:bg-zinc-800/60"
        >
          <GitBranch className="h-4 w-4 text-zinc-400" />
          Monorepo root
          <ExternalLink className="h-3 w-3 opacity-60" />
        </a>
      </section>

      {/* App cards */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          4 apps in the monorepo
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          {APPS.map((app) => (
            <a
              key={app.name}
              href={app.github}
              target="_blank"
              rel="noreferrer"
              className="flex flex-col gap-1.5 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 transition hover:border-zinc-700 hover:bg-zinc-800/60"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-100">{app.name}</span>
                <span className="font-mono text-xs text-zinc-500">{app.path}</span>
              </div>
              <p className="text-sm leading-relaxed text-zinc-400">{app.description}</p>
            </a>
          ))}
        </div>
      </section>

      {/* Interactive system DAG */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-zinc-500">
          Live system graph
        </h2>
        <ArchitectureClient
          graph={systemGraph}
          initialHealth={health}
          checkedAt={checkedAt}
          nodeLive={nodeLive}
          live_data={live_data}
        />
      </section>
    </div>
  );
}
