import { NextRequest, NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain API not configured." }, { status: 503 });
  }
  const { searchParams } = request.nextUrl;
  const res = await fetch(`${auth.root}/admin/expenses/rollup?${searchParams.toString()}`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
