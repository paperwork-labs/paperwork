import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

/** Proxy GET /api/v1/admin/expenses — list with filter + cursor */
export async function GET(request: Request) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain not configured" }, { status: 503 });
  }
  const { searchParams } = new URL(request.url);
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

/** Proxy POST /api/v1/admin/expenses — create expense */
export async function POST(request: Request) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain not configured" }, { status: 503 });
  }
  const body = await request.formData();
  const params = new URLSearchParams();
  for (const [key, value] of body.entries()) {
    if (key !== "receipt") params.set(key, String(value));
  }
  const receipt = body.get("receipt") as File | null;

  const upstream = `${auth.root}/admin/expenses?${params.toString()}`;
  const upstreamForm = new FormData();
  if (receipt) upstreamForm.append("receipt", receipt);

  const res = await fetch(upstream, {
    method: "POST",
    headers: { "X-Brain-Secret": auth.secret },
    body: receipt ? upstreamForm : undefined,
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
