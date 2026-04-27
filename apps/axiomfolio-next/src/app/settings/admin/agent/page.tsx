import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { RequireAdmin } from "@/components/auth/RequireAdmin";
import AdminAgentClient from "@/components/admin/AdminAgentClient";

export default function AdminAgentPage() {
  return (
    <RequireAuthClient>
      <RequireAdmin>
        <AdminAgentClient />
      </RequireAdmin>
    </RequireAuthClient>
  );
}
