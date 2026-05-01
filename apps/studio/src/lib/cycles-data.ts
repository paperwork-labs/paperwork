import { headers } from "next/headers";

import workstreamsJson from "@/data/workstreams.json";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { getStudioPublicOrigin } from "@/lib/studio-public-url";
import {
  WorkstreamsBoardBrainEnvelopeSchema,
  WorkstreamsFileSchema,
} from "@/lib/workstreams/schema";
import type { WorkstreamsFile } from "@/lib/workstreams/schema";

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

export async function resolveStudioRequestBaseUrl(): Promise<string> {
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

export type StudioWorkstreamsBoardLoadSuccess = {
  ok: true;
  file: WorkstreamsFile;
  brainFreshnessBanner: string | null;
  bundledFallbackBanner: string | null;
  legacyBrainShapeBanner: string | null;
  staleDataBanner: string | null;
};

export type StudioWorkstreamsBoardLoadFailure = {
  ok: false;
  error: string;
};

export type StudioWorkstreamsBoardLoadResult =
  | StudioWorkstreamsBoardLoadSuccess
  | StudioWorkstreamsBoardLoadFailure;

/**
 * Single loader for Studio workstreams board data.
 * - Brain not configured: bundled `workstreams.json` only (no HTTP).
 * - Brain configured: loads via Brain `GET .../admin/workstreams-board` (server-to-server with
 *   `X-Brain-Secret`). SSR must not call Studio `/api/admin/workstreams` (no Clerk cookie → 401).
 */
export async function loadStudioWorkstreamsBoard(
  baseUrl: string,
): Promise<StudioWorkstreamsBoardLoadResult> {
  void baseUrl;
  const fallbackParsed = WorkstreamsFileSchema.parse(workstreamsJson);
  const fallbackUpdated = fallbackParsed.updated;

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return {
      ok: true,
      file: fallbackParsed,
      brainFreshnessBanner: null,
      bundledFallbackBanner: null,
      legacyBrainShapeBanner: null,
      staleDataBanner: null,
    };
  }

  try {
    const res = await fetch(`${auth.root}/admin/workstreams-board`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (!res.ok) {
      let msg = `Brain workstreams unavailable (HTTP ${res.status}).`;
      try {
        const text = await res.text();
        const j = JSON.parse(text) as { error?: string };
        if (typeof j?.error === "string" && j.error.trim()) {
          msg = j.error;
        }
      } catch {
        /* keep default */
      }
      return { ok: false, error: msg };
    }

    const raw: unknown = await res.json();
    const env = WorkstreamsBoardBrainEnvelopeSchema.safeParse(raw);
    if (env.success) {
      const e = env.data;
      const file = WorkstreamsFileSchema.parse({
        version: e.version,
        updated: e.updated,
        workstreams: e.workstreams,
      });
      return {
        ok: true,
        file,
        brainFreshnessBanner: `Last sync: ${relativeAgo(e.generated_at)} from Brain`,
        bundledFallbackBanner:
          e.source === "bundled-json-fallback"
            ? `Brain unreachable — showing bundled snapshot from ${bundledCommitLabel()}`
            : null,
        legacyBrainShapeBanner: null,
        staleDataBanner: null,
      };
    }

    const legacy = WorkstreamsFileSchema.safeParse(raw);
    if (legacy.success) {
      return {
        ok: true,
        file: legacy.data,
        brainFreshnessBanner: null,
        bundledFallbackBanner: null,
        legacyBrainShapeBanner:
          "Brain returned legacy board JSON (no freshness envelope). Refetch after Brain deploy.",
        staleDataBanner: null,
      };
    }

    return {
      ok: false,
      error: `Brain returned workstreams data that could not be parsed (last known bundle updated ${fallbackUpdated}).`,
    };
  } catch (e) {
    return {
      ok: false,
      error: e instanceof Error ? e.message : "Failed to fetch workstreams from Brain",
    };
  }
}
