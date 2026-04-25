import { redirect } from "next/navigation";

// Agents was merged into /admin/workflows (Track J, Week 1). Keep this redirect
// so bookmarks + old Brain memory references survive.
export default function AgentsRedirect(): never {
  redirect("/admin/workflows?tab=roster");
}
