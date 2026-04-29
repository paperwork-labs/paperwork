import { permanentRedirect } from "next/navigation";

// Content moved to Architecture → Analytics tab (WS-69 PR C). 308 permanent redirect.
export default function AnalyticsLegacyPage() {
  permanentRedirect("/admin/architecture?tab=analytics");
}
