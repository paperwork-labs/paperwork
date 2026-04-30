"use client";

import { useAuth } from "@clerk/nextjs";

import { BrainChat } from "@paperwork-labs/ui";

import TierGate from "@/components/billing/TierGate";

/**
 * Floating Brain chat for AxiomFolio (WS-76 PR-29).
 *
 * - **Tier**: wrapped in `TierGate` for `brain.native_chat` (Pro+ per `feature_catalog.py`).
 * - **Kill switch**: set `NEXT_PUBLIC_AXIOMFOLIO_BRAIN_CHAT=false` to hide the widget entirely.
 * - **Backend**: uses `/api/brain/process`, which forwards to Brain `POST /api/v1/brain/process`
 *   with Clerk bearer + `X-Brain-Secret`. Configure `BRAIN_*` and `AXIOMFOLIO_BRAIN_ORGANIZATION_ID`
 *   on the server (see route handler docstring).
 */
export function BrainChatPanel() {
  if (process.env.NEXT_PUBLIC_AXIOMFOLIO_BRAIN_CHAT === "false") {
    return null;
  }

  const { isLoaded, isSignedIn } = useAuth();
  if (!isLoaded || !isSignedIn) {
    return null;
  }

  return (
    <TierGate feature="brain.native_chat">
      <BrainChat
        apiUrl="/api/brain/process"
        productSlug="axiomfolio"
        visualVariant="dark"
        personaPin="trading"
      />
    </TierGate>
  );
}
