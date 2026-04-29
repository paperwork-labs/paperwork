import { permanentRedirect } from "next/navigation";

// Content moved to Infrastructure → Secrets tab (WS-69 PR C). 308 permanent redirect.
export default function SecretsLegacyPage() {
  permanentRedirect("/admin/infrastructure?tab=secrets");
}
