import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import MarketEducationClient from "@/components/market/MarketEducationClient";

export default function MarketEducationPage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
        <MarketEducationClient />
      </Suspense>
    </RequireAuthClient>
  );
}
