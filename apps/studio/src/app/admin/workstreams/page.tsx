import { Suspense } from "react";

import workstreamsJson from "@/data/workstreams.json";
import { computeWorkstreamsBoardKpis } from "@/lib/tracker-reconcile";
import { headers } from "next/headers";
import {
  WorkstreamsBoardBrainEnvelopeSchema,
  WorkstreamsFileSchema,
} from "@/lib/workstreams/schema";
import { getStudioPublicOrigin } from "@/lib/studio-public-url";

import { WorkstreamsBoardClient } from "./workstreams-client";

export const dynamic = "force-dynamic";

async function resolveBaseUrl(): Promise<string> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  if (!host) {
    return getStudioPublicOrigin();
  }
  const proto =
    h.get("x-forwarded-proto") ??
    (host.startsWith("localhost") || host.startsWith("127.") ? "http" : "https");
  return `${proto}://${host}`;
}

function relativeAgo(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "unknown time";
  const sec = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 48) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

function bundledCommitLabel(): string {
  const sha = process.env.VERCEL_GIT_COMMIT_SHA?.trim();
  if (sha && sha.length >= 7) return sha.slice(0, 7);
  return "local-dev";
}

function staleBannerFromBuildSnapshot(updatedIso: string): string {
  return `Live Brain unavailable — showing last build's snapshot from ${updatedIso}.`;
}

export default async function AdminWorkstreamsPage() {
  const fallbackParsed = WorkstreamsFileSchema.parse(workstreamsJson);
  const fallbackUpdated = fallbackParsed.updated;

  let parsedFile = fallbackParsed;
  let staleDataBanner: string | null = null;
  let brainFreshnessBanner: string | null = null;
  let bundledFallbackBanner: string | null = null;
  let legacyBrainShapeBanner: string | null = null;

  const base = await resolveBaseUrl();
  try {
    const res = await fetch(`${base}/api/admin/workstreams`, { cache: "no-store" });
    if (res.ok) {
      const raw: unknown = await res.json();
      const env = WorkstreamsBoardBrainEnvelopeSchema.safeParse(raw);
      if (env.success) {
        const e = env.data;
        parsedFile = WorkstreamsFileSchema.parse({
          version: e.version,
          updated: e.updated,
          workstreams: e.workstreams,
        });
        brainFreshnessBanner = `Last sync: ${relativeAgo(e.generated_at)} from Brain`;
        if (e.source === "bundled-json-fallback") {
          bundledFallbackBanner = `Brain unreachable — showing bundled snapshot from ${bundledCommitLabel()}`;
        }
      } else {
        const legacy = WorkstreamsFileSchema.safeParse(raw);
        if (legacy.success) {
          parsedFile = legacy.data;
          legacyBrainShapeBanner =
            "Brain returned legacy board JSON (no freshness envelope). Refetch after Brain deploy.";
        } else {
          staleDataBanner = staleBannerFromBuildSnapshot(fallbackUpdated);
        }
      }
    } else {
      bundledFallbackBanner = `Brain unreachable — showing bundled snapshot from ${bundledCommitLabel()}`;
    }
  } catch {
    bundledFallbackBanner = `Brain unreachable — showing bundled snapshot from ${bundledCommitLabel()}`;
  }

  const kpis = computeWorkstreamsBoardKpis(parsedFile);

  return (
    <Suspense fallback={<div className="animate-pulse text-sm text-zinc-500">Loading workstreams…</div>}>
      <WorkstreamsBoardClient
        kpis={kpis}
        parsedFile={parsedFile}
        staleDataBanner={staleDataBanner}
        brainFreshnessBanner={brainFreshnessBanner}
        bundledFallbackBanner={bundledFallbackBanner}
        legacyBrainShapeBanner={legacyBrainShapeBanner}
      />
    </Suspense>
  );
}
