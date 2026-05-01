import { BrainClient } from "@/lib/brain-client";
import type { GoalsJson } from "@/lib/goals-metrics";
import { GoalsBrainDisconnected, GoalsClient } from "./goals-client";

export const dynamic = "force-dynamic";

export const metadata = { title: "Goals & OKRs — Studio" };

export default async function GoalsPage() {
  let liveGoals: GoalsJson | null = null;

  const brain = BrainClient.fromEnv();
  if (brain) {
    try {
      liveGoals = await brain.getGoals();
    } catch {
      liveGoals = null;
    }
  }

  const visible =
    liveGoals == null
      ? null
      : {
          ...liveGoals,
          objectives: liveGoals.objectives.filter(
            (o) => !(o as { archived_at?: string | undefined }).archived_at,
          ),
        };

  return visible ? (
    <GoalsClient data={visible} />
  ) : (
    <GoalsBrainDisconnected brainConfigured={brain != null} />
  );
}
