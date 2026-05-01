import { NextRequest, NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

/**
 * TODO(PB-8): Brain does not yet expose POST /api/v1/admin/conversations/{id}/reply
 * (body: { persona_slug, content }). See apis/brain/app/routers/conversations.py — only
 * /messages exists today. This route is ready to proxy once Brain adds the endpoint.
 */
function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const reqBody = await req.text();
  const res = await fetch(`${auth.root}/admin/conversations/${id}/reply`, {
    method: "POST",
    headers: {
      "X-Brain-Secret": auth.secret,
      "Content-Type": req.headers.get("Content-Type") ?? "application/json",
    },
    body: reqBody,
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
