/** Hub filter bucket derived from markdown `doc_kind` frontmatter. */
export type HubDocCategory =
  | "philosophy"
  | "architecture"
  | "strategy"
  | "runbook"
  | "playbook"
  | "decision-log"
  | "uncategorized";

export type FreshnessLevel = "fresh" | "aging" | "stale" | "unknown";

const WPM = 200;

/** Reading time at 200 wpm, minutes rounded up. Zero words → 0. */
export function computeReadTime(wordCount: number): number {
  if (wordCount <= 0) return 0;
  return Math.ceil(wordCount / WPM);
}

function parseReviewDate(lastReviewed: string): number | null {
  const t = Date.parse(`${lastReviewed.trim()}T12:00:00.000Z`);
  return Number.isNaN(t) ? null : t;
}

/**
 * Freshness from `last_reviewed` (YYYY-MM-DD). No date → unknown.
 * - fresh: under 60 days
 * - aging: 60–180 days inclusive
 * - stale: over 180 days
 */
export function computeFreshness(lastReviewed: string | null): FreshnessLevel {
  if (!lastReviewed?.trim()) return "unknown";
  const reviewedAt = parseReviewDate(lastReviewed);
  if (reviewedAt === null) return "unknown";
  const days = (Date.now() - reviewedAt) / 86_400_000;
  if (days < 60) return "fresh";
  if (days <= 180) return "aging";
  return "stale";
}

export function docKindToHubCategory(docKindRaw: unknown): HubDocCategory {
  const k = typeof docKindRaw === "string" ? docKindRaw.trim().toLowerCase() : "";
  if (!k) return "uncategorized";
  if (k === "philosophy") return "philosophy";
  if (k === "architecture") return "architecture";
  if (k === "plan" || k === "sprint") return "strategy";
  if (k === "runbook") return "runbook";
  if (k === "handoff" || k === "checklist" || k === "template") return "playbook";
  if (k === "decision") return "decision-log";
  return "uncategorized";
}

export const HUB_CATEGORY_LABEL: Record<HubDocCategory, string> = {
  philosophy: "Philosophy",
  architecture: "Architecture",
  strategy: "Strategy",
  runbook: "Runbook",
  playbook: "Playbook",
  "decision-log": "Decision Log",
  uncategorized: "Triage",
};

/** Approximate whole months since last_reviewed for stale copy. */
export function monthsSinceReview(lastReviewed: string): number {
  const reviewedAt = parseReviewDate(lastReviewed);
  if (reviewedAt === null) return 0;
  const days = (Date.now() - reviewedAt) / 86_400_000;
  return Math.max(1, Math.round(days / 30));
}
