import { Suspense } from "react";

import { BrainStatusBanner } from "@/components/admin/hq/BrainStatusBanner";
import { AdminRouteFallback } from "./admin-route-fallback";
import { AdminLayoutClient } from "./admin-layout-client";
import { BrainContextProvider } from "@/lib/brain-context";
import { getE2EMutableConversationsBadge } from "@/lib/e2e-conversations-mutable";
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

async function fetchExpensesPendingCount(): Promise<number | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses?status=pending&count_only=true&limit=1`,
      { headers: { "X-Brain-Secret": auth.secret }, cache: "no-store" },
    );
    if (!res.ok) return null;
    const json = await res.json();
    return json.success ? (json.data?.total ?? 0) : null;
  } catch {
    return null;
  }
}

async function fetchExpensesFlaggedCount(): Promise<number | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;
  try {
    const res = await fetch(
      `${auth.root}/admin/expenses?status=flagged&count_only=true&limit=1`,
      { headers: { "X-Brain-Secret": auth.secret }, cache: "no-store" },
    );
    if (!res.ok) return null;
    const json = await res.json();
    return json.success ? (json.data?.total ?? 0) : null;
  } catch {
    return null;
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
      ? getE2EMutableConversationsBadge()
      : (await fetchFounderPendingFromBrain()) ?? {
          count: c.totalPending,
          hasCritical: c.critical > 0,
        };

  const [pendingCount, flaggedCount] = await Promise.all([
    fetchExpensesPendingCount(),
    fetchExpensesFlaggedCount(),
  ]);
  const expensesCountsUnknown = pendingCount === null || flaggedCount === null;
  const p = pendingCount ?? 0;
  const f = flaggedCount ?? 0;
  const totalNeedsAction = p + f;
  const expensesPending =
    !expensesCountsUnknown && totalNeedsAction > 0
      ? { count: totalNeedsAction, hasCritical: f > 0 }
      : null;

  return (
    <BrainContextProvider>
      <AdminLayoutClient
        founderPending={founderPending}
        expensesPending={expensesPending}
        expensesCountsUnknown={expensesCountsUnknown}
      >
        <>
          <Suspense fallback={null}>
            <BrainStatusBanner />
          </Suspense>
          <Suspense fallback={<AdminRouteFallback />}>{children}</Suspense>
        </>
      </AdminLayoutClient>
    </BrainContextProvider>
  );
}
