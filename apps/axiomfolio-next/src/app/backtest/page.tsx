import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import BacktestLabClient from "@/components/backtest/BacktestLabClient";

export default function BacktestPage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
        <BacktestLabClient />
      </Suspense>
    </RequireAuthClient>
  );
}
