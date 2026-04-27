import dynamic from "next/dynamic";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { RequireAdmin } from "@/components/auth/RequireAdmin";
import { AdminLoadingSkeleton } from "@/components/ui/AdminLoadingSkeleton";

const SystemStatusClient = dynamic(
  () => import("@/components/system/SystemStatusClient"),
  {
    loading: () => <AdminLoadingSkeleton />,
  },
);

export default function SystemStatusPage() {
  return (
    <RequireAuthClient>
      <RequireAdmin>
        <SystemStatusClient />
      </RequireAdmin>
    </RequireAuthClient>
  );
}
