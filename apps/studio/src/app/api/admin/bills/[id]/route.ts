import { NextRequest, NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { error: "Brain API not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 }
  );
}

type RouteParams = { params: Promise<{ id: string }> };

export async function GET(_request: NextRequest, { params }: RouteParams) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();
  const { id } = await params;
  const res = await fetch(`${auth.root}/admin/bills/${id}`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();
  const { id } = await params;
  const body = await request.text();
  const res = await fetch(`${auth.root}/admin/bills/${id}`, {
    method: "PATCH",
    headers: {
      "X-Brain-Secret": auth.secret,
      "Content-Type": "application/json",
    },
    body,
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

export async function DELETE(_request: NextRequest, { params }: RouteParams) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();
  const { id } = await params;
  const res = await fetch(`${auth.root}/admin/bills/${id}`, {
    method: "DELETE",
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
