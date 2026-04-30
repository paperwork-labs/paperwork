import { NextRequest, NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

/** Read-only proxy in PR N. PR O extends with PUT. */
export async function GET() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain API not configured." }, { status: 503 });
  }
  const res = await fetch(`${auth.root}/admin/expenses/rules`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

export async function PUT(request: NextRequest) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain API not configured." }, { status: 503 });
  }
  const body = await request.text();
  const res = await fetch(`${auth.root}/admin/expenses/rules`, {
    method: "PUT",
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
