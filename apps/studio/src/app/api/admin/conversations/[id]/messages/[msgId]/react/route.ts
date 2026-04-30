import { NextRequest, NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { e2eToggleReactionOnMessage } from "@/lib/e2e-conversations-mutable";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string; msgId: string }> },
) {
  const { id, msgId } = await params;

  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    let body: Record<string, unknown>;
    try {
      body = (await req.json()) as Record<string, unknown>;
    } catch {
      return NextResponse.json({ success: false, error: "Invalid JSON body" }, { status: 400 });
    }
    const emoji = typeof body.emoji === "string" ? body.emoji : "";
    const participant_id = typeof body.participant_id === "string" ? body.participant_id : "";
    if (!emoji || !participant_id) {
      return NextResponse.json({ success: false, error: "emoji and participant_id required" }, { status: 400 });
    }
    const updated = e2eToggleReactionOnMessage(id, msgId, emoji, participant_id);
    if (!updated) {
      return NextResponse.json({ success: false, error: "Message not found" }, { status: 404 });
    }
    return NextResponse.json({ success: true, data: updated });
  }

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const reqBody = await req.text();
  const res = await fetch(`${auth.root}/admin/conversations/${id}/messages/${msgId}/react`, {
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
