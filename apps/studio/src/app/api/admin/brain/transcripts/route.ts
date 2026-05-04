import { NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

/** Proxies Brain `GET /api/v1/admin/transcripts` (cursor pagination). */
export async function GET(req: Request): Promise<NextResponse> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return NextResponse.json({ error: "Brain is not configured for Studio" }, { status: 503 });
  }

  const url = new URL(req.url);
  const outgoing = new URLSearchParams();
  const limit = url.searchParams.get("limit");
  const cursor = url.searchParams.get("cursor");
  if (limit !== null && limit !== "") outgoing.set("limit", limit);
  if (cursor !== null && cursor !== "") outgoing.set("cursor", cursor);
  const qs = outgoing.toString();
  const path = qs === "" ? `${auth.root}/admin/transcripts` : `${auth.root}/admin/transcripts?${qs}`;

  let res: Response;
  try {
    res = await fetch(path, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Network error calling Brain transcripts list." },
      { status: 502 },
    );
  }

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
