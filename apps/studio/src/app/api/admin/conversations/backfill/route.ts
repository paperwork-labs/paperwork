import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

/** Proxies Brain founder-actions → Conversations idempotent backfill (WS-76 PR-2). */
export async function POST() {
  if (process.env.STUDIO_E2E_FIXTURE === "1") {
    return NextResponse.json({
      success: true,
      data: { created: 0, source_kind: "e2e_fixture", parse_error: null },
    });
  }

  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  const res = await fetch(`${auth.root}/admin/conversations/_backfill-founder-actions`, {
    method: "POST",
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}
