import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Discovery hint for Brain hierarchy proxies. Prefer concrete paths such as:
 * `POST /api/admin/epics/goals`, `PATCH /api/admin/epics/goals/{id}`, …
 */
export async function GET() {
  return NextResponse.json({
    ok: true,
    proxy: "/api/admin/epics/[...path] → Brain `{BRAIN_API_URL}/api/v1/admin/{path}`",
    examples: ["goals", "goals/:goalId", "epics", "epics/:id", "sprints", "tasks"],
  });
}
