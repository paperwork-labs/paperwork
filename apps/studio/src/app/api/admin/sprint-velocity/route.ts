import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    {
      success: false,
      error: "Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET).",
    },
    { status: 503 },
  );
}

export async function GET() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();
  const res = await fetch(`${auth.root}/admin/sprint-velocity`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}

export async function POST() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();
  const res = await fetch(`${auth.root}/admin/sprint-velocity/recompute`, {
    method: "POST",
    headers: { "X-Brain-Secret": auth.secret },
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
