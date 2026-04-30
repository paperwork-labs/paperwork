import { Suspense } from "react";

import { AdminLayoutClient } from "./admin-layout-client";
import { getE2EConversationsBadge } from "@/lib/e2e-conversations-fixture";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import founderData from "@/data/founder-actions.json";

export const dynamic = "force-dynamic";

async function fetchFounderPendingFromBrain(): Promise<{
  count: number;
  hasCritical: boolean;
} | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(
      `${auth.root}/admin/conversations/unread-count?filter=needs-action`,
      { headers: { "X-Brain-Secret": auth.secret }, cache: "no-store" },
    );
    if (!res.ok) return null;
    const json = (await res.json()) as {
      success?: boolean;
      data?: { count?: number; has_critical?: boolean };
    };
    if (!json.success || json.data == null) return null;
    return {
      count: typeof json.data.count === "number" ? json.data.count : 0,
      hasCritical: Boolean(json.data.has_critical),
    };
  } catch {
    return null;
  }
}

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

  const founderPending: { count: number; hasCritical: boolean } =
    process.env.STUDIO_E2E_FIXTURE === "1"
      ? getE2EConversationsBadge()
      : (await fetchFounderPendingFromBrain()) ?? {
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
