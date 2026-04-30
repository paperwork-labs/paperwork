import { Suspense } from "react";

import { AdminLayoutClient } from "./admin-layout-client";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import founderData from "@/data/founder-actions.json";

export const dynamic = "force-dynamic";

async function fetchExpensesPendingCount(): Promise<number> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return 0;
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses?status=pending&count_only=true&limit=1`,
      { headers: { "X-Brain-Secret": auth.secret }, cache: "no-store" }
    );
    if (!res.ok) return 0;
    const json = await res.json();
    return json.success ? (json.data?.total ?? 0) : 0;
  } catch {
    return 0;
  }
}

async function fetchExpensesFlaggedCount(): Promise<number> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return 0;
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses?status=flagged&count_only=true&limit=1`,
      { headers: { "X-Brain-Secret": auth.secret }, cache: "no-store" }
    );
    if (!res.ok) return 0;
    const json = await res.json();
    return json.success ? (json.data?.total ?? 0) : 0;
  } catch {
    return 0;
  }
}

export default async function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const c = founderData.counts;
  if (
    !c ||
    typeof c.critical !== "number" ||
    typeof c.totalPending !== "number"
  ) {
    throw new Error(
      "Admin layout: founder-actions.json must include counts.critical and counts.totalPending (numbers). Run apps/studio/scripts/sync-founder-actions.mjs.",
    );
  }
  const founderPending = {
    count: c.totalPending,
    hasCritical: c.critical > 0,
  };

  const [pendingCount, flaggedCount] = await Promise.all([
    fetchExpensesPendingCount(),
    fetchExpensesFlaggedCount(),
  ]);
  const totalNeedsAction = pendingCount + flaggedCount;
  const expensesPending =
    totalNeedsAction > 0
      ? { count: totalNeedsAction, hasCritical: flaggedCount > 0 }
      : null;

  return (
    <AdminLayoutClient founderPending={founderPending} expensesPending={expensesPending}>
      <Suspense fallback={null}>{children}</Suspense>
    </AdminLayoutClient>
  );
}
