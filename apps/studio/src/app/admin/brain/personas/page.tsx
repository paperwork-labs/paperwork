import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default function PersonasRedirect() {
  redirect("/admin/people?view=workspace");
}
