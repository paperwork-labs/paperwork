import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

/** Proxies GET /api/v1/admin/audits — secrets stay server-side (F-042). */
export async function GET() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain is not configured for Studio" }, { status: 503 });
  }
  const res = await fetch(`${auth.root}/admin/audits`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
