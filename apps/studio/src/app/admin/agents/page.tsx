import { permanentRedirect } from "next/navigation";

// Agents roster lives under Architecture → Flows. Avoid `/admin/workflows` intermediate redirect.
export default function AgentsRedirect(): never {
  permanentRedirect("/admin/architecture?tab=flows");
}
