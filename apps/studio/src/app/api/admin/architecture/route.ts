import { NextResponse } from "next/server";
import { systemGraph, probeAll } from "@/lib/system-graph";

export const dynamic = "force-dynamic";

export async function GET() {
  const health = await probeAll(systemGraph);
  return NextResponse.json(
    {
      health,
      checkedAt: new Date().toISOString(),
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
