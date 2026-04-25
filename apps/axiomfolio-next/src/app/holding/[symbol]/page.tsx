"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";

const HoldingDetailClient = dynamic(() => import("./HoldingDetailClient"), {
  ssr: false,
  loading: () => <div className="p-6 text-sm text-muted-foreground">Loading chart…</div>,
});

export default function HoldingSymbolPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <HoldingDetailClient />
    </Suspense>
  );
}
