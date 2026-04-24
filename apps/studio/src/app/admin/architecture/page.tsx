import { systemGraph, probeAll } from "@/lib/system-graph";
import ArchitectureClient from "./architecture-client";

export const dynamic = "force-dynamic";

export default async function ArchitecturePage() {
  const health = await probeAll(systemGraph);
  const checkedAt = new Date().toISOString();

  return (
    <ArchitectureClient
      graph={systemGraph}
      initialHealth={health}
      checkedAt={checkedAt}
    />
  );
}
