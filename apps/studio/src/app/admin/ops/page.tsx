import { redirect } from "next/navigation";

// Ops was merged into /admin/workflows (Track J, Week 1). Keep this redirect
// around indefinitely — bookmarks + old Brain memory references survive.
export default function OpsRedirect(): never {
  redirect("/admin/workflows?tab=activity");
}
