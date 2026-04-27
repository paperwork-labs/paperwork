import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import HistoricalImportWizardClient from "@/components/settings/HistoricalImportWizardClient";

export default function HistoricalImportPage() {
  return (
    <RequireAuthClient>
      <HistoricalImportWizardClient />
    </RequireAuthClient>
  );
}
