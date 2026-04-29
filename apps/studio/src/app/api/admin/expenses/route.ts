import { NextRequest, NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { error: "Brain API not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 }
  );
}

export async function GET(request: NextRequest) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const { searchParams } = request.nextUrl;
  const upstream = `${auth.root}/admin/expenses?${searchParams.toString()}`;
  const res = await fetch(upstream, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

/** Multipart passthrough — forward form body + optional receipt to Brain. */
export async function POST(request: NextRequest) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const formData = await request.formData();
  const res = await fetch(`${auth.root}/admin/expenses`, {
    method: "POST",
    headers: { "X-Brain-Secret": auth.secret },
    body: formData,
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
