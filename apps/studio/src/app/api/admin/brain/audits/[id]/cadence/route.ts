import { NextRequest, NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

export async function PUT(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain is not configured for Studio" }, { status: 503 });
  }
  const { id } = await ctx.params;
  const body = await req.text();
  const res = await fetch(`${auth.root}/admin/audits/${encodeURIComponent(id)}/cadence`, {
    method: "PUT",
    headers: { "X-Brain-Secret": auth.secret, "Content-Type": "application/json" },
    body,
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
