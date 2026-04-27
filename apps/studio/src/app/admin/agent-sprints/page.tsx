import { getAgentSprintsToday } from "@/lib/command-center";

import AgentSprintsClient from "./agent-sprints-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AgentSprintsPage() {
  const initial = await getAgentSprintsToday();
  const initialError = initial ? null : "Brain not wired or no data — set BRAIN_API_URL + BRAIN_API_SECRET.";
  return <AgentSprintsClient initial={initial} initialError={initialError} />;
}
