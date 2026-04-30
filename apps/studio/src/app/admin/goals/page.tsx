import goalsData from "@/data/goals.json";
import { GoalsClient } from "./goals-client";

export const dynamic = "force-static";

export const metadata = { title: "Goals & OKRs — Studio" };

export default function GoalsPage() {
  return <GoalsClient data={goalsData} />;
}
