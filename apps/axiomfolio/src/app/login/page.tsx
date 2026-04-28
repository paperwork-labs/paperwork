import { redirect } from "next/navigation";

import { safeAppReturnPath } from "@/lib/safe-app-return-path";

/**
 * Legacy `/login` — WS-14 sends visitors to Clerk. Preserves safe `returnTo` as
 * `redirect_url` for the sign-in flow.
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ returnTo?: string }>;
}) {
  const sp = await searchParams;
  const safe = safeAppReturnPath(sp.returnTo ?? null);
  const q = new URLSearchParams();
  if (safe) q.set("redirect_url", safe);
  const suffix = q.size ? `?${q.toString()}` : "";
  redirect(`/sign-in${suffix}`);
}
