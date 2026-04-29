import { permanentRedirect } from "next/navigation";

// n8n is decommissioned (PR J). Redirects to Architecture → Integrations tab (WS-69 PR C).
export default function N8nMirrorLegacyPage() {
  permanentRedirect("/admin/architecture?tab=integrations");
}
