import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import MarketIntelligenceClient from "@/components/market/MarketIntelligenceClient";

export default function MarketIntelligencePage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
        <MarketIntelligenceClient />
      </Suspense>
    </RequireAuthClient>
  );
}
