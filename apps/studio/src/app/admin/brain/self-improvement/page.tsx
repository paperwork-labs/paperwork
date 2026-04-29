import { SelfImprovementClient } from "./self-improvement-client";
import { loadSelfImprovementPayload } from "@/lib/self-improvement";

export const dynamic = "force-dynamic";

export default async function BrainSelfImprovementPage() {
  const payload = await loadSelfImprovementPayload();
  const brainConfigured = Boolean(
    process.env.BRAIN_API_URL?.trim() && process.env.BRAIN_API_SECRET?.trim(),
  );
  return <SelfImprovementClient payload={payload} brainConfigured={brainConfigured} />;
}
