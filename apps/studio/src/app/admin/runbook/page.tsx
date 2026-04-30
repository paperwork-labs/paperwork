import { parseDay0Runbook } from "@/lib/day0-runbook";
import { RunbookClient } from "./runbook-client";

export const metadata = { title: "Runbook — Studio" };

export default function RunbookPage() {
  const data = parseDay0Runbook();
  return <RunbookClient data={data} />;
}
