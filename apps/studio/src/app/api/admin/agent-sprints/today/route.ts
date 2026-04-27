import { NextResponse } from "next/server";

import { getAgentSprintsToday } from "@/lib/command-center";

export const dynamic = "force-dynamic";

export async function GET() {
  const payload = await getAgentSprintsToday();
  if (!payload) {
    return NextResponse.json(
      { ok: false, error: "Brain not configured or request failed (BRAIN_API_URL / BRAIN_API_SECRET)." },
      { status: 503 },
    );
  }
  return NextResponse.json({ ok: true, data: payload });
}
