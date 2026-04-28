import workstreamsJson from "@/data/workstreams.json";
import { headers } from "next/headers";
import {
  WorkstreamsFileSchema,
  computeKpis,
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

function staleBannerFromBuildSnapshot(updatedIso: string): string {
  return `Live Brain unavailable — showing last build's snapshot from ${updatedIso}.`;
}

export default async function AdminWorkstreamsPage() {
  const fallbackParsed = WorkstreamsFileSchema.parse(workstreamsJson);
  const fallbackUpdated = fallbackParsed.updated;

  let parsedFile = fallbackParsed;
  let staleDataBanner: string | null = null;

  const base = await resolveBaseUrl();
  try {
    const res = await fetch(`${base}/api/admin/workstreams`, { cache: "no-store" });
    if (res.ok) {
      const raw: unknown = await res.json();
      const live = WorkstreamsFileSchema.safeParse(raw);
      if (live.success) {
        parsedFile = live.data;
      } else {
        staleDataBanner = staleBannerFromBuildSnapshot(fallbackUpdated);
      }
    } else {
      staleDataBanner = staleBannerFromBuildSnapshot(fallbackUpdated);
    }
  } catch {
    staleDataBanner = staleBannerFromBuildSnapshot(fallbackUpdated);
  }

  const kpis = computeKpis(parsedFile);

  return (
    <WorkstreamsBoardClient
      kpis={kpis}
      parsedFile={parsedFile}
      staleDataBanner={staleDataBanner}
    />
  );
}
