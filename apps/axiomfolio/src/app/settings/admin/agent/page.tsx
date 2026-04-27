import dynamic from "next/dynamic";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { RequireAdmin } from "@/components/auth/RequireAdmin";
import { AdminLoadingSkeleton } from "@/components/ui/AdminLoadingSkeleton";

const AdminAgentClient = dynamic(
  () => import("@/components/admin/AdminAgentClient"),
  {
    loading: () => <AdminLoadingSkeleton />,
  },
);

export default function AdminAgentPage() {
  return (
    <RequireAuthClient>
      <RequireAdmin>
        <AdminAgentClient />
      </RequireAdmin>
    </RequireAuthClient>
  );
}
