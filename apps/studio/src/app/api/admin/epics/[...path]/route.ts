import { NextRequest, NextResponse } from "next/server";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export const dynamic = "force-dynamic";

function notConfigured() {
  return NextResponse.json(
    { success: false, error: "Brain is not configured (BRAIN_API_URL / BRAIN_API_SECRET)." },
    { status: 503 },
  );
}

async function proxy(req: NextRequest, segments: string[]) {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return notConfigured();

  if (!segments?.length) {
    return NextResponse.json(
      { success: false, error: "Missing path segment after /api/admin/epics/" },
      { status: 400 },
    );
  }

  const sub = segments.join("/");
  const qs = req.nextUrl.search;
  const url = `${auth.root}/admin/${sub}${qs}`;

  const method = req.method;
  let bodyText: string | undefined;
  if (method !== "GET" && method !== "HEAD") {
    bodyText = await req.text();
  }

  const headers: Record<string, string> = { "X-Brain-Secret": auth.secret };
  const ctype = req.headers.get("Content-Type");
  if (bodyText && bodyText.length > 0) {
    headers["Content-Type"] = ctype ?? "application/json";
  }

  const res = await fetch(url, {
    method,
    headers,
    body: bodyText && bodyText.length > 0 ? bodyText : undefined,
    cache: "no-store",
  });

  const outType = res.headers.get("Content-Type") || "application/json";
  return new NextResponse(await res.arrayBuffer(), {
    status: res.status,
    headers: {
      "Content-Type": outType,
    },
  });
}

async function delegate(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export const GET = delegate;
export const POST = delegate;
export const PATCH = delegate;
export const PUT = delegate;
export const DELETE = delegate;
