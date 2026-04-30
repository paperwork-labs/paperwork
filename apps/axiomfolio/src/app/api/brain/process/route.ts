import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * BFF for Brain `POST /api/v1/brain/process`.
 *
 * Requires server env:
 * - `BRAIN_API_URL` — Brain base URL (no trailing slash), same as Studio.
 * - `BRAIN_API_SECRET` — value for `X-Brain-Secret`.
 * - `AXIOMFOLIO_BRAIN_ORGANIZATION_ID` — must match the Clerk-linked Paperwork org for callers.
 *
 * Optional kill-switch: omit secrets to keep route returning 503 until Brain is wired.
 */
export async function POST(request: Request) {
  const { userId, getToken } = await auth();
  if (!userId) {
    return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });
  }

  const token = await getToken();
  if (!token) {
    return NextResponse.json(
      { success: false, error: "Missing Clerk session token for Brain." },
      { status: 401 },
    );
  }

  const brainUrl = process.env.BRAIN_API_URL?.replace(/\/$/, "");
  const secret = process.env.BRAIN_API_SECRET;
  const organizationId = process.env.AXIOMFOLIO_BRAIN_ORGANIZATION_ID?.trim();

  if (!brainUrl || !secret || !organizationId) {
    return NextResponse.json(
      { success: false, error: "Brain proxy is not configured on this deployment." },
      { status: 503 },
    );
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ success: false, error: "Invalid JSON body" }, { status: 400 });
  }

  if (typeof body.message !== "string" || !body.message.trim()) {
    return NextResponse.json({ success: false, error: "message is required" }, { status: 400 });
  }

  const forward: Record<string, unknown> = {
    organization_id: organizationId,
    message: body.message,
    channel: typeof body.channel === "string" ? body.channel : "axiomfolio",
  };

  if (typeof body.channel_id === "string") forward.channel_id = body.channel_id;
  if (typeof body.thread_id === "string") forward.thread_id = body.thread_id;
  if (Array.isArray(body.thread_context)) forward.thread_context = body.thread_context;
  if (typeof body.persona_pin === "string") forward.persona_pin = body.persona_pin;
  if (typeof body.strategy === "string") forward.strategy = body.strategy;
  if (typeof body.request_id === "string") forward.request_id = body.request_id;
  if (typeof body.user_id === "string") forward.user_id = body.user_id;

  let res: Response;
  try {
    res = await fetch(`${brainUrl}/api/v1/brain/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Brain-Secret": secret,
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(forward),
      signal: AbortSignal.timeout(120_000),
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Brain fetch failed";
    return NextResponse.json({ success: false, error: msg }, { status: 502 });
  }

  const raw = await res.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    return NextResponse.json(
      { success: false, error: `Brain returned non-JSON (HTTP ${res.status})` },
      { status: 502 },
    );
  }

  return NextResponse.json(parsed, { status: res.ok ? 200 : res.status });
}
