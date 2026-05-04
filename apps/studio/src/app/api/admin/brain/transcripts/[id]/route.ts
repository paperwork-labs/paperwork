import { NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

/** Proxies Brain `GET /api/v1/admin/transcripts/{id}` */
export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain is not configured for Studio" }, { status: 503 });
  }

  const { id } = await ctx.params;
  const safeId = encodeURIComponent(id.trim());

  let res: Response;
  try {
    res = await fetch(`${auth.root}/admin/transcripts/${safeId}`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Network error calling Brain transcript detail." },
      { status: 502 },
    );
  }

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
