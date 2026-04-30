import { NextRequest, NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

export async function POST(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain is not configured for Studio" }, { status: 503 });
  }
  const { id } = await ctx.params;
  const res = await fetch(`${auth.root}/admin/audits/${encodeURIComponent(id)}/run`, {
    method: "POST",
    headers: { "X-Brain-Secret": auth.secret, "Content-Type": "application/json" },
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
