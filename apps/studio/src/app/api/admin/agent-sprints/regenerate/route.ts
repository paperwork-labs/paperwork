import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function normalizeBaseUrl(raw: string | undefined) {
  if (!raw) return undefined;
  return raw.trim().replace(/\/+$/, "");
}

function brainServiceRoot() {
  const raw = normalizeBaseUrl(process.env.BRAIN_API_URL);
  if (!raw) return undefined;
  return raw.replace(/\/api\/v1\/?$/, "");
}

export async function POST() {
  const base = brainServiceRoot();
  const secret = process.env.BRAIN_API_SECRET?.trim();
  if (!base || !secret) {
    return NextResponse.json({ ok: false, error: "Brain not wired." }, { status: 503 });
  }
  const res = await fetch(`${base}/internal/agent-sprints/regenerate`, {
    method: "POST",
    headers: { "X-Brain-Secret": secret },
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json({ ok: false, error: body?.error ?? res.statusText }, { status: res.status });
  }
  return NextResponse.json(body);
}
