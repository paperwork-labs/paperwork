import { NextRequest, NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function apiRoot() {
  const auth = getBrainAdminFetchOptions();
  return auth.ok ? auth : null;
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const auth = apiRoot();
  if (!auth) {
    return NextResponse.json(
      { error: "Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET)." },
      { status: 503 },
    );
  }
  const sub = ((await ctx.params).path ?? []).join("/");
  if (!sub) {
    return NextResponse.json({ error: "Missing path" }, { status: 400 });
  }
  const target = new URL(`${auth.root}/admin/personas/${sub}`);
  req.nextUrl.searchParams.forEach((v, k) => target.searchParams.set(k, v));
  const res = await fetch(target, { headers: { "X-Brain-Secret": auth.secret }, cache: "no-store" });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
