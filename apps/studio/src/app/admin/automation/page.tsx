import { permanentRedirect } from "next/navigation";

// Folded into Brain → Self-Improvement (WS-69 PR C). 308 permanent redirect.
export default function AutomationLegacyPage() {
  permanentRedirect("/admin/brain/self-improvement?tab=automation-state");
}
