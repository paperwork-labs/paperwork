import goalsData from "@/data/goals.json";
import { BrainClient } from "@/lib/brain-client";
import type { GoalsJson } from "@/lib/goals-metrics";
import { GoalsClient } from "./goals-client";

export const dynamic = "force-dynamic";

export const metadata = { title: "Goals & OKRs — Studio" };

export default async function GoalsPage() {
  let data: GoalsJson = goalsData;
  let brainUnavailable = true;

  const brain = BrainClient.fromEnv();
  if (brain) {
    try {
      data = await brain.getGoals();
      brainUnavailable = false;
    } catch {
      data = goalsData;
      brainUnavailable = true;
    }
  }

  return <GoalsClient data={data} brainUnavailable={brainUnavailable} />;
}
