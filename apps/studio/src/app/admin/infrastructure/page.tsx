import { getInfrastructureView } from "@/lib/command-center";
import { getE2EInfrastructureFixture } from "@/lib/e2e-infra-mock";
import InfraClient from "./infra-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function InfrastructurePage() {
  const checkedAt = new Date().toISOString();
  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    const e2e = getE2EInfrastructureFixture();
    return (
      <InfraClient
        initialServices={e2e.services}
        initialPlatformSummary={e2e.platformSummary}
        initialPlatformPartial={e2e.platformPartial}
        initialCheckedAt={checkedAt}
      />
    );
  }
  const view = await getInfrastructureView();
  return (
    <InfraClient
      initialServices={view.services}
      initialPlatformSummary={view.platformSummary}
      initialPlatformPartial={view.platformPartial}
      initialCheckedAt={checkedAt}
    />
  );
}
