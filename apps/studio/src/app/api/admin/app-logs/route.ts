/**
 * Studio proxy for Brain-owned application logs (WS-69 PR M).
 *
 * GET  /api/admin/app-logs  — forward query params to Brain GET /api/v1/admin/logs
 * POST /api/admin/app-logs  — forward body to Brain POST /api/v1/admin/logs/ingest
 *
 * Adds X-Brain-Secret server-side so the secret never reaches the browser.
 */

import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function brainRoot(): string | null {
  const raw = process.env.BRAIN_API_URL?.trim().replace(/\/+$/, "");
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

function brainSecret(): string | null {
  return process.env.BRAIN_API_SECRET?.trim() || null;
}

export async function GET(req: NextRequest): Promise<NextResponse> {
  const root = brainRoot();
  const secret = brainSecret();
  if (!root || !secret) {
    return NextResponse.json({ error: "Brain API not configured" }, { status: 503 });
  }

  const qs = req.nextUrl.search;
  const url = `${root}/admin/logs${qs}`;

  try {
    const res = await fetch(url, {
      headers: { "X-Brain-Secret": secret },
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to reach Brain API", detail: String(err) },
      { status: 502 },
    );
  }
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  const root = brainRoot();
  const secret = brainSecret();
  if (!root || !secret) {
    return NextResponse.json({ error: "Brain API not configured" }, { status: 503 });
  }

  try {
    const body = await req.json();
    const res = await fetch(`${root}/admin/logs/ingest`, {
      method: "POST",
      headers: { "X-Brain-Secret": secret, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to reach Brain API", detail: String(err) },
      { status: 502 },
    );
  }
}
