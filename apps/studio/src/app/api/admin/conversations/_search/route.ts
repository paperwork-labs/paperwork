import { NextRequest, NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

export async function POST(req: NextRequest) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q") ?? "";
  const limit = searchParams.get("limit") ?? "20";

  const res = await fetch(
    `${auth.root}/admin/conversations/_search?q=${encodeURIComponent(q)}&limit=${limit}`,
    {
      method: "POST",
      headers: { "X-Brain-Secret": auth.secret },
    },
  );
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
