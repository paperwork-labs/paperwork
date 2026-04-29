import { permanentRedirect } from "next/navigation";

// Founder actions are now Brain → Conversations with ?filter=needs-action (WS-69 PR C).
// 308 permanent redirect.
export default function FounderActionsLegacyPage() {
  permanentRedirect("/admin/brain/conversations?filter=needs-action");
}
