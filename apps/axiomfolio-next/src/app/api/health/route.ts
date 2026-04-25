import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    app: "axiomfolio-next",
    features: {
      enabled: process.env.NEXT_PUBLIC_AXIOMFOLIO_NEXT_ENABLED === "true",
      vite_origin: process.env.NEXT_PUBLIC_AXIOMFOLIO_VITE_ORIGIN ?? null,
    },
    ts: new Date().toISOString(),
  });
}
