import { NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

type RouteParams = { params: Promise<{ slug: string }> };

export async function GET(_request: Request, { params }: RouteParams) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json(
      { error: "Brain API not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
      { status: 503 },
    );
  }
  const { slug } = await params;
  const url = `${auth.root}/admin/employees/${encodeURIComponent(slug)}/activity`;
  const res = await fetch(url, {
    method: "GET",
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
