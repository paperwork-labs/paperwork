import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

/**
 * Proxies Brain `GET /api/v1/admin/workstreams-board` (X-Brain-Secret).
 * Returns the raw workstreams file JSON for `WorkstreamsFileSchema`.
 */
export async function GET() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json(
      {
        error: "Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET).",
      },
      { status: 503 },
    );
  }

  const res = await fetch(`${auth.root}/admin/workstreams-board`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });

  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
