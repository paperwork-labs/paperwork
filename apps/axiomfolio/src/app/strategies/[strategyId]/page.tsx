"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";

const StrategyDetailClient = dynamic(
  () => import("@/components/strategies/StrategyDetailClient"),
  {
    ssr: false,
    loading: () => (
      <div className="p-6 text-sm text-muted-foreground">Loading strategy…</div>
    ),
  }
);

export default function StrategyDetailPage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
        <StrategyDetailClient />
      </Suspense>
    </RequireAuthClient>
  );
}
