import { NextResponse } from "next/server";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import type { BrainSchedulerJob, BrainSchedulersBffPayload } from "@/types/brain-schedulers";

export const dynamic = "force-dynamic";

/** Base origin for Brain paths outside `/api/v1/*` (e.g. `GET /internal/schedulers`). */
function brainAppOriginFromAdminRoot(apiV1Root: string): string {
  return apiV1Root.replace(/\/api\/v1$/i, "").replace(/\/+$/, "");
}

function parseJobsPayload(rawUnknown: unknown): BrainSchedulerJob[] | null {
  if (!Array.isArray(rawUnknown)) return null;

  const out: BrainSchedulerJob[] = [];
  for (const rowUnknown of rawUnknown) {
    if (typeof rowUnknown !== "object" || rowUnknown === null) continue;
    const row = rowUnknown as Record<string, unknown>;

    const idRaw = typeof row.id === "string" ? row.id : row.job_id;
    if (typeof idRaw !== "string" || idRaw.trim() === "") continue;

    let next_run: string | null = null;
    if (row.next_run === null || row.next_run === undefined) {
      next_run = null;
    } else if (typeof row.next_run === "string") {
      next_run = row.next_run;
    } else continue;

    const trig = typeof row.trigger === "string" ? row.trigger : "";
    const enabled = typeof row.enabled === "boolean" ? row.enabled : true;
    const classification =
      typeof row.classification === "string" ? row.classification : "unknown";

    let last_completed_at: string | null | undefined;
    const lc = row.last_completed_at ?? row.last_run;
    if (typeof lc === "string") {
      last_completed_at = lc;
    } else if (lc === null) {
      last_completed_at = null;
    }

    let run_count: number | null | undefined;
    if (typeof row.run_count === "number" && Number.isFinite(row.run_count)) {
      run_count = Math.trunc(row.run_count);
    } else if (row.run_count === null) {
      run_count = null;
    }

    const job: BrainSchedulerJob = {
      id: idRaw.trim(),
      next_run,
      trigger: trig,
      enabled,
      classification,
    };

    if (last_completed_at !== undefined) job.last_completed_at = last_completed_at;
    if (run_count !== undefined) job.run_count = run_count;
    out.push(job);
  }
  out.sort((a, b) => a.id.localeCompare(b.id));
  return out;
}

/**
 * Proxy Brain `GET /internal/schedulers` (read-only on Brain; unauthenticated upstream).
 * Studio gate matches other `/api/admin/brain/*` routes: `BRAIN_API_URL` + `BRAIN_API_SECRET`.
 */
export async function GET(): Promise<NextResponse<BrainSchedulersBffPayload>> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    const body: BrainSchedulersBffPayload = {
      ok: false,
      empty: false,
      code: "upstream",
      message:
        "Brain is not configured for Studio (set BRAIN_API_URL and BRAIN_API_SECRET to proxy scheduler introspection).",
      httpStatus: 503,
    };
    return NextResponse.json(body, { status: 503 });
  }

  const origin = brainAppOriginFromAdminRoot(auth.root);

  let res: Response;
  try {
    res = await fetch(`${origin}/internal/schedulers`, {
      cache: "no-store",
    });
  } catch (e) {
    const body: BrainSchedulersBffPayload = {
      ok: false,
      empty: false,
      code: "upstream",
      message: e instanceof Error ? e.message : "Network error calling Brain `/internal/schedulers`.",
      httpStatus: 502,
    };
    return NextResponse.json(body, { status: 502 });
  }

  let rawUnknown: unknown;
  try {
    rawUnknown = await res.json();
  } catch {
    const body: BrainSchedulersBffPayload = {
      ok: false,
      empty: false,
      code: "invalid_shape",
      message: `Brain responded with non-JSON (HTTP ${res.status}).`,
      httpStatus: res.status || 502,
    };
    return NextResponse.json(body, { status: 502 });
  }

  if (!res.ok) {
    let msg = "";
    const errField = typeof rawUnknown === "object" && rawUnknown !== null ? (rawUnknown as { detail?: unknown }).detail : undefined;
    if (typeof errField === "string") msg = errField;
    else if (typeof rawUnknown !== "object" || rawUnknown === null) msg = String(rawUnknown);

    const body: BrainSchedulersBffPayload = {
      ok: false,
      empty: false,
      code: "upstream",
      message: msg || `Brain /internal/schedulers returned HTTP ${res.status}.`,
      httpStatus: res.status,
    };
    return NextResponse.json(body, { status: 502 });
  }

  const parsed = parseJobsPayload(rawUnknown);
  if (parsed === null) {
    const body: BrainSchedulersBffPayload = {
      ok: false,
      empty: false,
      code: "invalid_shape",
      message: "Brain /internal/schedulers returned a JSON value that was not an array.",
      httpStatus: 502,
    };
    return NextResponse.json(body, { status: 502 });
  }

  if (parsed.length === 0) {
    const body: BrainSchedulersBffPayload = {
      ok: false,
      empty: true,
      code: "no_jobs",
      message:
        "Brain reported zero APScheduler jobs (scheduler may be off or unreachable). Confirm BRAIN_SCHEDULER_ENABLED on Brain. Track T1.7-followup for last-run freshness export.",
    };
    return NextResponse.json(body, { status: 200 });
  }

  const hasLastCompleted = parsed.some(
    (j) =>
      typeof j.last_completed_at === "string" &&
      j.last_completed_at.trim() !== "",
  );

  const body: BrainSchedulersBffPayload = {
    ok: true,
    jobs: parsed,
    lastRunExported: hasLastCompleted,
    sourcePath: "/internal/schedulers",
  };

  return NextResponse.json(body, { status: 200 });
}
