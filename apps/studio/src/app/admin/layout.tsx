import { AdminLayoutClient } from "./admin-layout-client";
import founderData from "@/data/founder-actions.json";

export default function AdminLayout({
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

  return (
    <AdminLayoutClient founderPending={founderPending}>
      {children}
    </AdminLayoutClient>
  );
}
