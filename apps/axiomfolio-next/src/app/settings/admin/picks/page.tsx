import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { RequireAdmin } from "@/components/auth/RequireAdmin";
import PicksValidatorClient from "@/components/admin/PicksValidatorClient";

export default function AdminPicksPage() {
  return (
    <RequireAuthClient>
      <RequireAdmin>
        <PicksValidatorClient />
      </RequireAdmin>
    </RequireAuthClient>
  );
}
