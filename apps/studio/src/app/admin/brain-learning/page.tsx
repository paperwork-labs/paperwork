import { permanentRedirect } from "next/navigation";

// Folded into Brain → Self-Improvement → Learning tab (WS-69 PR C). 308 permanent redirect.
export default function LegacyBrainLearningPage() {
  permanentRedirect("/admin/brain/self-improvement?tab=learning");
}
