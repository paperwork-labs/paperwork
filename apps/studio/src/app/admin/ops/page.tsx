import { permanentRedirect } from "next/navigation";

// Ops was merged into Architecture → Flows. Avoid `/admin/workflows` hop (308) that drops query tabs.
export default function OpsRedirect(): never {
  permanentRedirect("/admin/architecture?tab=flows");
}
