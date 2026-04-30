import { permanentRedirect } from "next/navigation";

// Legacy founder-actions now redirects to the Day-0 runbook (WS-76 PR-4).
// 308 permanent redirect.
export default function FounderActionsLegacyPage() {
  permanentRedirect("/admin/runbook");
}
