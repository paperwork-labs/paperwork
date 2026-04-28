import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json(
      {
        success: false,
        error: "Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET).",
      },
      { status: 503 },
    );
  }
  const res = await fetch(`${auth.root}/admin/quota/github-actions`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
