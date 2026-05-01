import { ExternalLink, GitBranch, Layers, BookOpen } from "lucide-react";
import { getArchitecturePayload } from "@/lib/get-architecture-payload";
import { systemGraph } from "@/lib/system-graph";
import ArchitectureClient from "../architecture-client";

export const dynamic = "force-dynamic";

export default async function OverviewTab() {
  const { health, checkedAt, nodeLive, live_data } = await getArchitecturePayload();

  return (
    <div className="space-y-8">
      {/* Interactive system DAG — hero */}
      <section>
        <p className="mb-4 max-w-2xl text-xs text-zinc-500">
          Nodes show health, hosting badges, and deploy times where live data is wired. Click through to Studio;
          Shift+click keeps the detail drawer for deep dives.
        </p>
        <ArchitectureClient
          graph={systemGraph}
          initialHealth={health}
          checkedAt={checkedAt}
          nodeLive={nodeLive}
          live_data={live_data}
        />
      </section>

      {/* Quick links — compact footer strip */}
      <section className="border-t border-zinc-800/60 pt-5">
        <div className="flex flex-wrap gap-2">
          <a
            href="https://github.com/paperwork-labs/paperwork/blob/main/docs/ARCHITECTURE.md"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-800/80 bg-zinc-900/40 px-2.5 py-1.5 text-xs text-zinc-400 transition hover:border-zinc-700 hover:bg-zinc-800/50 hover:text-zinc-200"
          >
            <BookOpen className="h-3.5 w-3.5 text-zinc-500" />
            Architecture docs
            <ExternalLink className="h-3 w-3 opacity-50" />
          </a>
          <a
            href="https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-800/80 bg-zinc-900/40 px-2.5 py-1.5 text-xs text-zinc-400 transition hover:border-zinc-700 hover:bg-zinc-800/50 hover:text-zinc-200"
          >
            <Layers className="h-3.5 w-3.5 text-zinc-500" />
            Brain architecture
            <ExternalLink className="h-3 w-3 opacity-50" />
          </a>
          <a
            href="https://github.com/paperwork-labs/paperwork"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-800/80 bg-zinc-900/40 px-2.5 py-1.5 text-xs text-zinc-400 transition hover:border-zinc-700 hover:bg-zinc-800/50 hover:text-zinc-200"
          >
            <GitBranch className="h-3.5 w-3.5 text-zinc-500" />
            Monorepo root
            <ExternalLink className="h-3 w-3 opacity-50" />
          </a>
        </div>
      </section>
    </div>
  );
}
