import { NextResponse } from "next/server";
import { z } from "zod";

const BodySchema = z.object({
  ordered_ids: z.array(z.string().min(1)),
});

function reorderDisabled(): boolean {
  return process.env.NEXT_PUBLIC_WORKSTREAMS_REORDER_ENABLED !== "true";
}

export async function POST(req: Request) {
  if (reorderDisabled()) {
    return NextResponse.json(
      { error: "reorder feature flag off" },
      { status: 503 },
    );
  }

  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const parsed = BodySchema.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "validation failed", issues: parsed.error.flatten() },
      { status: 400 },
    );
  }

  const brainUrl = process.env.BRAIN_API_URL?.replace(/\/$/, "");
  const token = process.env.BRAIN_INTERNAL_TOKEN;
  if (!brainUrl || !token) {
    return NextResponse.json(
      { error: "Brain reorder URL or internal token not configured" },
      { status: 500 },
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${brainUrl}/api/v1/workstreams/reorder`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(parsed.data),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: "Brain reorder request failed", detail: message },
      { status: 502 },
    );
  }

  const rawBody = await upstream.text();
  let payload: unknown = rawBody;
  try {
    payload = rawBody ? JSON.parse(rawBody) : null;
  } catch {
    payload = { raw: rawBody };
  }

  if (!upstream.ok) {
    return NextResponse.json(
      {
        error: "Brain reorder failed",
        status: upstream.status,
        body: payload,
      },
      { status: upstream.status >= 400 ? upstream.status : 502 },
    );
  }

  return NextResponse.json(payload, { status: 202 });
}
