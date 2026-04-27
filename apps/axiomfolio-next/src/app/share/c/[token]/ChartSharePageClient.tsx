"use client";

import dynamic from "next/dynamic";

const ChartShareClient = dynamic(() => import("@/components/share/ChartShareClient"), { ssr: false });

export default function ChartSharePageClient({ token }: { token: string }) {
  return <ChartShareClient token={token} />;
}
