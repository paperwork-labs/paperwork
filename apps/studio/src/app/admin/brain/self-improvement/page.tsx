import { Suspense } from "react";

import { SelfImprovementClient } from "./self-improvement-client";

export const metadata = {
  title: "Brain self-improvement",
};

export default function BrainSelfImprovementPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Brain self-improvement
        </h1>
        <p className="text-sm text-zinc-400">
          WS-64 loop telemetry: workstream candidates, self-merge graduation, PR outcomes, weekly retros,
          APScheduler jobs, and procedural memory — all read-only from Brain data.
        </p>
      </header>
      <Suspense
        fallback={
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400">
            Loading navigation…
          </div>
        }
      >
        <SelfImprovementClient />
      </Suspense>
    </div>
  );
}
