import { NextRequest, NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { getE2EMutableConversation } from "@/lib/e2e-conversations-mutable";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    const conv = getE2EMutableConversation(id);
    if (!conv) {
      return NextResponse.json({ success: false, error: "Conversation not found" }, { status: 404 });
    }
    return NextResponse.json({ success: true, data: conv });
  }

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const res = await fetch(`${auth.root}/admin/conversations/${id}`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
