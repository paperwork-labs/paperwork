import { NextRequest, NextResponse } from "next/server";

function apiRoot() {
  const raw = process.env.BRAIN_API_URL?.trim().replace(/\/+$/, "");
  return raw ? (raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`) : null;
}

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const root = apiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!root || !secret) {
    return NextResponse.json({ error: "Brain is not configured for Studio" }, { status: 503 });
  }
  const sub = ((await ctx.params).path ?? []).join("/");
  const target = new URL(`${root}/admin/logs${sub ? `/${sub}` : ""}`);
  req.nextUrl.searchParams.forEach((v, k) => target.searchParams.set(k, v));
  const res = await fetch(target, { headers: { "X-Brain-Secret": secret }, cache: "no-store" });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path?: string[] }> }) {
  const root = apiRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!root || !secret) {
    return NextResponse.json({ error: "Brain is not configured for Studio" }, { status: 503 });
  }
  const sub = ((await ctx.params).path ?? []).join("/");
  const target = new URL(`${root}/admin/logs${sub ? `/${sub}` : ""}`);
  const body = await req.text();
  const res = await fetch(target, {
    method: "POST",
    headers: {
      "X-Brain-Secret": secret,
      "Content-Type": req.headers.get("Content-Type") || "application/json",
    },
    body: body || undefined,
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
