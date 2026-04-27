import dynamic from "next/dynamic";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { RequireAdmin } from "@/components/auth/RequireAdmin";
import { AdminLoadingSkeleton } from "@/components/ui/AdminLoadingSkeleton";

const PicksValidatorClient = dynamic(
  () => import("@/components/admin/PicksValidatorClient"),
  {
    loading: () => <AdminLoadingSkeleton />,
  },
);

export default function AdminPicksPage() {
  return (
    <RequireAuthClient>
      <RequireAdmin>
        <PicksValidatorClient />
      </RequireAdmin>
    </RequireAuthClient>
  );
}
