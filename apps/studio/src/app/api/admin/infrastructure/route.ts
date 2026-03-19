import { NextResponse } from "next/server";
import { getInfrastructureStatus } from "@/lib/command-center";

export const dynamic = "force-dynamic";

export async function GET() {
  const services = await getInfrastructureStatus();
  const checkedAt = new Date().toISOString();
  return NextResponse.json({ services, checkedAt });
}
