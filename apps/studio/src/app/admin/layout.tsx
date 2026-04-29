import { AdminLayoutClient } from "./admin-layout-client";
import founderData from "@/data/founder-actions.json";

export default function AdminLayout({
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

  return (
    <AdminLayoutClient founderPending={founderPending}>
      {children}
    </AdminLayoutClient>
  );
}
