import { getArchitecturePayload } from "@/lib/get-architecture-payload";
import { systemGraph } from "@/lib/system-graph";
import ArchitectureClient from "./architecture-client";

export const dynamic = "force-dynamic";

export default async function ArchitecturePage() {
  const { health, checkedAt, nodeLive, live_data } = await getArchitecturePayload();

  return (
    <ArchitectureClient
      graph={systemGraph}
      initialHealth={health}
      checkedAt={checkedAt}
      nodeLive={nodeLive}
      live_data={live_data}
    />
  );
}
