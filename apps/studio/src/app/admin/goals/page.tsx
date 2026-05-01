import goalsData from "@/data/goals.json";

import { GoalsClient } from "./goals-client";
import { loadGoalsOperatingScore } from "./goals-operating-score";

export const dynamic = "force-dynamic";

export const metadata = { title: "Goals & OKRs — Studio" };

export default async function GoalsPage() {
  const operatingScore = await loadGoalsOperatingScore();
  return <GoalsClient data={goalsData} operatingScore={operatingScore} />;
}
