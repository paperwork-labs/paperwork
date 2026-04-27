import dynamic from "next/dynamic";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { AdminLoadingSkeleton } from "@/components/ui/AdminLoadingSkeleton";

const HistoricalImportWizardClient = dynamic(
  () => import("@/components/settings/HistoricalImportWizardClient"),
  {
    loading: () => <AdminLoadingSkeleton />,
  },
);

export default function HistoricalImportPage() {
  return (
    <RequireAuthClient>
      <HistoricalImportWizardClient />
    </RequireAuthClient>
  );
}
