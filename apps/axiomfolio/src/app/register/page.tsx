import { redirect } from "next/navigation";

/**
 * Legacy `/register` — WS-14 sends visitors to Clerk sign-up. Preserves `upgrade`
 * for pricing handoff (`PENDING_UPGRADE_KEY` is still written on the sign-up page
 * when that query is present — see Clerk flow / future app hooks).
 */
export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{ upgrade?: string }>;
}) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  if (sp.upgrade) q.set("upgrade", sp.upgrade);
  const suffix = q.size ? `?${q.toString()}` : "";
  redirect(`/sign-up${suffix}`);
}
