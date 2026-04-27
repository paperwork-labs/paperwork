import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Server-only proxy: Studio admin → Brain `/internal/secrets/*` (Bearer `BRAIN_INTERNAL_TOKEN`).
 * Example: `GET /api/brain/secrets/registry` → Brain `GET /internal/secrets/registry`.
 */
async function proxy(
  request: NextRequest,
  pathSegments: string[],
): Promise<NextResponse> {
  const base = process.env.BRAIN_API_URL?.replace(/\/$/, "");
  const token = process.env.BRAIN_INTERNAL_TOKEN?.trim();
  if (!base || !token) {
    return NextResponse.json(
      {
        ok: false,
        error:
          "Brain secrets proxy not configured — set BRAIN_API_URL and BRAIN_INTERNAL_TOKEN on Studio.",
      },
      { status: 503 },
    );
  }
  const sub = pathSegments.map(encodeURIComponent).join("/");
  const q = request.nextUrl.searchParams.toString();
  const url = `${base}/internal/secrets/${sub}${q ? `?${q}` : ""}`;
  const method = request.method;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  };
  if (method !== "GET" && method !== "HEAD") {
    const ct = request.headers.get("content-type");
    if (ct) {
      headers["Content-Type"] = ct;
    } else {
      headers["Content-Type"] = "application/json";
    }
  }
  const res = await fetch(url, {
    method,
    headers,
    body: method === "GET" || method === "HEAD" ? undefined : await request.text(),
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path: pathSeg } = await context.params;
  return proxy(request, pathSeg);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path: pathSeg } = await context.params;
  return proxy(request, pathSeg);
}
