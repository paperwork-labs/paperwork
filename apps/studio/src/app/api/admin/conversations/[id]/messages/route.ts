import { NextRequest, NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { e2eTryAppendMessage } from "@/lib/e2e-conversations-mutable";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json({ success: false, error: "Invalid JSON body" }, { status: 400 });
    }
    const o = body as Record<string, unknown>;
    const author = o.author as Parameters<typeof e2eTryAppendMessage>[1]["author"];
    const bodyMd = typeof o.body_md === "string" ? o.body_md : "";
    const attachments = Array.isArray(o.attachments)
      ? (o.attachments as Parameters<typeof e2eTryAppendMessage>[1]["attachments"])
      : [];
    const parent_message_id =
      typeof o.parent_message_id === "string"
        ? o.parent_message_id
        : o.parent_message_id === null
          ? null
          : undefined;

    const outcome = e2eTryAppendMessage(id, {
      author,
      body_md: bodyMd,
      attachments,
      parent_message_id,
    });
    if (!outcome.ok) {
      const status = outcome.kind === "parent_not_found" ? 400 : 404;
      const error =
        outcome.kind === "parent_not_found"
          ? `Parent message ${JSON.stringify(parent_message_id)} not found in conversation`
          : "Conversation not found";
      return NextResponse.json({ success: false, error }, { status });
    }
    return NextResponse.json({ success: true, data: outcome.message }, { status: 201 });
  }

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const reqBody = await req.text();
  const res = await fetch(`${auth.root}/admin/conversations/${id}/messages`, {
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
