import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default function RunbookRedirect() {
  redirect("/admin/docs/day-0-founder-actions");
}
