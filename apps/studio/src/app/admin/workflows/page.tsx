import { permanentRedirect } from "next/navigation";

// Folded into Architecture → Flows tab (WS-69 PR C). 308 permanent redirect.
export default function WorkflowsLegacyPage() {
  permanentRedirect("/admin/architecture?tab=flows");
}
