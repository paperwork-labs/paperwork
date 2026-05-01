import type { PersonaDispatchSummaryResponse } from "@/lib/brain-client";

/** Normalized shape for the Overview "Brain says..." copy. */
export type PersonaDispatchSummary = {
  totalDispatched: number;
  pendingReview: number;
  byPersona: { persona: string; count: number }[];
};

export function personaDispatchSummaryFromResponse(
  raw: PersonaDispatchSummaryResponse | null | undefined,
): PersonaDispatchSummary | null {
  if (!raw) return null;
  const byPersona = [...raw.personas]
    .sort((a, b) => b.dispatch_count - a.dispatch_count)
    .map((r) => ({ persona: r.persona_slug, count: r.dispatch_count }));
  const pendingReview = raw.personas.reduce((acc, p) => acc + p.pending_outcome_count, 0);
  return {
    totalDispatched: raw.dispatch_total,
    pendingReview,
    byPersona,
  };
}

export function brainNarrative(summary: PersonaDispatchSummary | null): string {
  if (!summary || summary.totalDispatched === 0) return "Brain is idle today.";
  const top = summary.byPersona[0];
  const pendingPart =
    summary.pendingReview > 0 ? ` ${summary.pendingReview} need your review.` : "";
  return `Dispatched ${summary.totalDispatched} task${summary.totalDispatched === 1 ? "" : "s"} today across ${summary.byPersona.length} persona${summary.byPersona.length === 1 ? "" : "s"}.${pendingPart}${top ? ` Top: ${top.persona} (${top.count}).` : ""}`;
}
