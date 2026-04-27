import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { BrainNotesCard } from "@/app/admin/secrets/secrets-client";

describe("BrainNotesCard", () => {
  it("matches snapshot", () => {
    const html = renderToStaticMarkup(
      <BrainNotesCard
        criticality="critical"
        driftSummary="Example drift note from Brain registry (no secret values shown)."
        lastBrainRotation="2026-04-27T12:00:00.000Z"
        episodes={[
          {
            event_type: "intake",
            event_at: "2026-04-27T12:00:00.000Z",
            summary: "Intake complete — canonical vault entry updated.",
          },
          {
            event_type: "drift_detected",
            event_at: "2026-04-26T10:00:00.000Z",
            summary: "Length/hash mismatch on one Vercel target.",
          },
        ]}
      />,
    );
    expect(html).toMatchSnapshot();
  });
});
