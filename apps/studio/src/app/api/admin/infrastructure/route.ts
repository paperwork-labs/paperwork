import { NextResponse } from "next/server";
import { cached, getInfrastructureStatus } from "@/lib/command-center";

export const dynamic = "force-dynamic";

const CACHE_TTL = 60_000;

export async function GET() {
  const services = await cached("admin:infrastructure", CACHE_TTL, getInfrastructureStatus);
  return NextResponse.json({ services, checkedAt: new Date().toISOString() });
}
