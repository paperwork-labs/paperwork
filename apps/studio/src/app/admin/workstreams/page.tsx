import { Suspense } from "react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { computeWorkstreamsBoardKpis } from "@/lib/tracker-reconcile";
import {
  loadStudioWorkstreamsBoard,
  resolveStudioRequestBaseUrl,
} from "@/lib/cycles-data";

import { WorkstreamsBoardClient } from "./workstreams-client";

export const dynamic = "force-dynamic";

export default async function AdminWorkstreamsPage() {
  const base = await resolveStudioRequestBaseUrl();
  const loaded = await loadStudioWorkstreamsBoard(base);

  if (!loaded.ok) {
    return (
      <div className="space-y-6">
        <HqPageHeader
          title="Workstreams"
          subtitle="Cross-cutting work logs across the company"
        />
        <div
          role="alert"
          className="rounded-lg border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-100"
        >
          {loaded.error}
        </div>
      </div>
    );
  }

  const kpis = computeWorkstreamsBoardKpis(loaded.file);

  return (
    <Suspense fallback={<div className="animate-pulse text-sm text-zinc-500">Loading workstreams…</div>}>
      <WorkstreamsBoardClient
        kpis={kpis}
        parsedFile={loaded.file}
        staleDataBanner={loaded.staleDataBanner}
        brainFreshnessBanner={loaded.brainFreshnessBanner}
        bundledFallbackBanner={loaded.bundledFallbackBanner}
        legacyBrainShapeBanner={loaded.legacyBrainShapeBanner}
      />
    </Suspense>
  );
}
