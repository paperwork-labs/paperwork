// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RunbookItem = {
  id: number;
  task: string;
  time: string;
  unblocks: string;
  done: boolean;
};

export type RunbookSection = {
  title: string;
  items: RunbookItem[];
};

export type RunbookData = {
  sections: RunbookSection[];
  total: number;
  completed: number;
  remaining: number;
  estTimeLeftMin: number;
  /**
   * Populated only when BRAIN_API_URL is configured and the request fails.
   * Callers should render an error banner when this field is non-null.
   * Null means "no error" — either Brain API succeeded or it is not configured.
   */
  sourceError?: string | null;
};

// ---------------------------------------------------------------------------
// Snapshot import (bundled at build time by scripts/snapshot-runbook.ts)
// ---------------------------------------------------------------------------

import runbookSnapshot from "@/data/runbook-snapshot.json";

const SNAPSHOT = runbookSnapshot as RunbookData;

// ---------------------------------------------------------------------------
// Brain API overlay
// ---------------------------------------------------------------------------

/**
 * Returns runbook data.
 *
 * - If BRAIN_API_URL is NOT set: returns bundled snapshot silently (production
 *   bootstrap path until Brain API ships).
 * - If BRAIN_API_URL is set and the request succeeds: returns live data.
 * - If BRAIN_API_URL is set but the request FAILS: returns snapshot data
 *   WITH sourceError populated so the caller can render an error banner.
 *   This is NOT a silent fallback.
 */
export async function parseDay0Runbook(): Promise<RunbookData> {
  const brainApiUrl = process.env.BRAIN_API_URL;

  if (!brainApiUrl) {
    return SNAPSHOT;
  }

  try {
    const res = await fetch(`${brainApiUrl}/admin/runbook`, {
      cache: "no-store",
      headers: { "X-Brain-Secret": process.env.BRAIN_API_SECRET ?? "" },
    });
    if (!res.ok) {
      return {
        ...SNAPSHOT,
        sourceError: `Brain API /admin/runbook returned ${res.status} ${res.statusText}`,
      };
    }
    const json = (await res.json()) as { success?: boolean; data?: RunbookData; error?: string };
    if (!json.success || !json.data) {
      return {
        ...SNAPSHOT,
        sourceError: json.error ?? "Brain API returned no runbook data.",
      };
    }
    return { ...json.data, sourceError: null };
  } catch (e) {
    return {
      ...SNAPSHOT,
      sourceError: e instanceof Error ? e.message : "Brain API request failed.",
    };
  }
}
