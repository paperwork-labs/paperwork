import { NextResponse } from "next/server";
import { getArchitecturePayload } from "@/lib/get-architecture-payload";

export const dynamic = "force-dynamic";

export async function GET() {
  const payload = await getArchitecturePayload();
  return NextResponse.json(
    {
      health: payload.health,
      checkedAt: payload.checkedAt,
      nodeLive: payload.nodeLive,
      live_data: payload.live_data,
    },
    {
      headers: {
        "Cache-Control": "private, s-maxage=30, stale-while-revalidate=60",
      },
    },
  );
}
