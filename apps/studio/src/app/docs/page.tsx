import { redirect } from "next/navigation";

// Track N consolidated all markdown browsing into /admin/docs, which reads
// docs/_index.yaml for taxonomy and enforces the philosophy lock. Keep
// this public route as a redirect so links in old PRs still land somewhere
// useful.
export default function PublicDocsRedirect() {
  redirect("/admin/docs");
}
