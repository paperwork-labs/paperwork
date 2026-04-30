import { existsSync, readFileSync } from "fs";
import path from "path";

function resolveFounderActionsJsonPath(): string | null {
  const candidates = [
    path.join(process.cwd(), "src", "data", "founder-actions.json"),
    path.join(process.cwd(), "apps", "studio", "src", "data", "founder-actions.json"),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return null;
}

/**
 * Validate founder-actions.json on disk (Studio canonical source).
 * Used so a corrupt / missing file surfaces as an error state instead of a silent empty inbox.
 */
export function readFounderActionsJsonFromDisk():
  | { ok: true; parsed: FounderActionsPayload }
  | { ok: false; message: string } {
  const p = resolveFounderActionsJsonPath();
  if (!p) {
    return { ok: false, message: "founder-actions.json not found on disk (expected under apps/studio/src/data/)." };
  }
  try {
    const raw = readFileSync(p, "utf8");
    const parsed = JSON.parse(raw) as FounderActionsPayload;
    if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.tiers)) {
      return { ok: false, message: "founder-actions.json is missing a valid `tiers` array." };
    }
    return { ok: true, parsed };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, message: `Could not read founder-actions.json: ${msg}` };
  }
}

export type FounderActionsPayload = {
  tiers?: Array<{
    id?: string;
    items?: Array<{
      title?: string;
      why?: string;
      where?: string;
      steps?: string[];
      verification?: string;
      eta?: string;
      source?: string;
      urgency?: string;
    }>;
  }>;
  counts?: { critical?: number; operational?: number; totalPending?: number };
};

export function countFounderActionItems(payload: FounderActionsPayload): number {
  let n = 0;
  for (const tier of payload.tiers ?? []) {
    for (const item of tier.items ?? []) {
      if (String(item.title ?? "").trim()) n += 1;
    }
  }
  return n;
}

export function founderActionsJsonHasPendingItems(payload: FounderActionsPayload): boolean {
  return countFounderActionItems(payload) > 0;
}
