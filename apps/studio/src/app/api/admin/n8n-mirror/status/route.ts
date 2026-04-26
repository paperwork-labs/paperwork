import { NextResponse } from "next/server";
import { getN8nMirrorSchedulerStatus } from "@/lib/command-center";

export const dynamic = "force-dynamic";

export async function GET() {
  const status = await getN8nMirrorSchedulerStatus();
  const checkedAt = new Date().toISOString();
  if (!status) {
    return NextResponse.json(
      { ok: false, status: null, checkedAt, error: "Brain not wired or status unavailable" },
      { status: 503 },
    );
  }
  return NextResponse.json({ ok: true, status, checkedAt });
}
