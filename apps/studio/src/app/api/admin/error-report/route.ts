import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    {
      success: false,
      error: "Brain is not configured for Studio (BRAIN_API_URL / BRAIN_API_SECRET).",
    },
    { status: 503 },
  );
}

export async function POST(req: Request) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: "Invalid JSON." }, { status: 400 });
  }

  const res = await fetch(`${auth.root}/admin/memory/error-capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Brain-Secret": auth.secret,
    },
    body: JSON.stringify(raw),
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
