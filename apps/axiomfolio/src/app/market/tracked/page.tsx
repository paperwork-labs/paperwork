import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import MarketTrackedClient from "@/components/market/MarketTrackedClient";

export default function MarketTrackedPage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
        <MarketTrackedClient />
      </Suspense>
    </RequireAuthClient>
  );
}
