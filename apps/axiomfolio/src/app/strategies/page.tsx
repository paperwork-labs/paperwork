import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import StrategiesClient from "@/components/strategies/StrategiesClient";

export default function StrategiesPage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
        <StrategiesClient />
      </Suspense>
    </RequireAuthClient>
  );
}
