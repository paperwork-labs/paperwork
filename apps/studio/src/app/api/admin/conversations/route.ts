import { NextRequest, NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { e2eCreateConversation, getE2EMutableListPage } from "@/lib/e2e-conversations-mutable";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

export async function GET(req: NextRequest) {
  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    return NextResponse.json({ success: true, data: getE2EMutableListPage() });
  }

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const { searchParams } = new URL(req.url);
  const upstream = new URL(`${auth.root}/admin/conversations`);
  for (const [k, v] of searchParams.entries()) {
    upstream.searchParams.set(k, v);
  }

  const res = await fetch(upstream.toString(), {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

export async function POST(req: NextRequest) {
  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    try {
      const raw = (await req.json()) as Record<string, unknown>;
      const data = e2eCreateConversation(raw);
      return NextResponse.json({ success: true, data }, { status: 201 });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Invalid compose payload";
      return NextResponse.json({ success: false, error: msg }, { status: 400 });
    }
  }

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const body = await req.text();
  const res = await fetch(`${auth.root}/admin/conversations`, {
    method: "POST",
    headers: {
      "X-Brain-Secret": auth.secret,
      "Content-Type": req.headers.get("Content-Type") ?? "application/json",
    },
    body,
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
