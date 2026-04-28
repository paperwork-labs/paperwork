import workstreamsJson from "@/data/workstreams.json";
import {
  WorkstreamsFileSchema,
  computeKpis,
} from "@/lib/workstreams/schema";

import { WorkstreamsBoardClient } from "./workstreams-client";

export const dynamic = "force-static";
export const revalidate = 300;

export default async function AdminWorkstreamsPage() {
  const parsedFile = WorkstreamsFileSchema.parse(workstreamsJson);
  const kpis = computeKpis(parsedFile);

  return <WorkstreamsBoardClient kpis={kpis} parsedFile={parsedFile} />;
}
