import { NextResponse } from "next/server";
import { getE2EMutableConversationsBadge } from "@/lib/e2e-conversations-mutable";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

/** Returns { count, has_critical } for sidebar + PWA badge (WS-76 PR-2 extends shape). */
export async function GET() {
  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    const b = getE2EMutableConversationsBadge();
    return NextResponse.json({
      success: true,
      data: { count: b.count, has_critical: b.hasCritical },
    });
  }

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const res = await fetch(`${auth.root}/admin/conversations/unread-count`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
