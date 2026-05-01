import {
  BrainClient,
  BrainClientError,
} from "@/lib/brain-client";

import type { GoalsOperatingScorePayload } from "./goals-operating-types";

export async function loadGoalsOperatingScore(): Promise<GoalsOperatingScorePayload> {
  const client = BrainClient.fromEnv();
  if (!client) return { kind: "unconfigured" };
  try {
    const data = await client.getOperatingScore();
    return { kind: "live", data };
  } catch (e) {
    const message =
      e instanceof BrainClientError ? e.message : "Failed to load operating score";
    return { kind: "error", message };
  }
}
