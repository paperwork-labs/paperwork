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

export async function GET() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();
  const res = await fetch(`${auth.root}/admin/operating-score`, {
    headers: { "X-Brain-Secret": auth.secret },
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}

export async function POST(req: Request) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    body = {};
  }
  const action =
    typeof body === "object" && body !== null && "action" in body
      ? (body as { action?: unknown }).action
      : undefined;
  if (action !== "recompute") {
    return NextResponse.json(
      { success: false, error: "Expected JSON body { \"action\": \"recompute\" }." },
      { status: 400 },
    );
  }

  const res = await fetch(`${auth.root}/admin/operating-score/recompute`, {
    method: "POST",
    headers: { "X-Brain-Secret": auth.secret },
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
