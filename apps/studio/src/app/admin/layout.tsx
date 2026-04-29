import { AdminLayoutClient } from "./admin-layout-client";
import founderData from "@/data/founder-actions.json";
import { fetchPendingCount } from "@/lib/expenses";

export default async function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const c = founderData.counts;
  const founderPending =
    typeof c.critical === "number" && typeof c.totalPending === "number"
      ? {
          count: c.totalPending,
          hasCritical: c.critical > 0,
        }
      : null;

  // Live expense pending count for sidebar badge; 0 on Brain unavailability
  const expensesPendingCount = await fetchPendingCount().catch(() => 0);

  return (
    <AdminLayoutClient
      founderPending={founderPending}
      expensesPendingCount={expensesPendingCount}
    >
      {children}
    </AdminLayoutClient>
  );
}
