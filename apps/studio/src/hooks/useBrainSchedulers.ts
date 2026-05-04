"use client";

import { useCallback, useEffect, useState } from "react";

import type { BrainSchedulerJob } from "@/types/brain-schedulers";

export type BrainSchedulersLoaded =
  | {
      status: "data";
      jobs: BrainSchedulerJob[];
      lastRunExported: boolean;
      sourcePath: "/internal/schedulers";
    }
  | {
      status: "empty";
      code: "unconfigured" | "no_jobs";
      message: string;
    };

type BrainSchedulersFetchState =
  | { loading: true; data: undefined; error: null }
  | { loading: false; data: BrainSchedulersLoaded; error: null }
  | { loading: false; data: undefined; error: Error };

async function fetchSchedulersPayload(): Promise<BrainSchedulersLoaded> {
  const res = await fetch("/api/admin/brain/schedulers", {
    credentials: "same-origin",
    cache: "no-store",
  });

  let jsonUnknown: unknown;
  try {
    jsonUnknown = await res.json();
  } catch {
    throw new Error(`Brain schedulers proxy returned unreadable JSON (HTTP ${res.status}).`);
  }

  const j = jsonUnknown as Record<string, unknown>;

  if (!res.ok) {
    const msg =
      typeof j.message === "string"
        ? j.message
        : typeof j.error === "string"
          ? j.error
          : `Request failed (${res.status}).`;
    throw new Error(msg);
  }

  if (j.ok === false && j.empty === true && typeof j.message === "string") {
    const code = j.code === "no_jobs" ? "no_jobs" : "unconfigured";
    return { status: "empty", code, message: j.message };
  }

  if (j.ok !== true || !Array.isArray(j.jobs)) {
    throw new Error(
      typeof j.message === "string"
        ? j.message
        : "Brain schedulers proxy returned an unexpected envelope.",
    );
  }

  const jobsUnknown = j.jobs as unknown[];
  const lastRunExported = typeof j.lastRunExported === "boolean" ? j.lastRunExported : false;
  const jobs: BrainSchedulerJob[] = [];

  for (const rowUnknown of jobsUnknown) {
    if (typeof rowUnknown !== "object" || rowUnknown === null) continue;
    const row = rowUnknown as Record<string, unknown>;
    const idRaw = row.id ?? row.job_id;
    if (typeof idRaw !== "string" || idRaw.trim() === "") continue;
    const nextRunRaw = row.next_run;
    let next_run: string | null = null;
    if (nextRunRaw === null || nextRunRaw === undefined) {
      next_run = null;
    } else if (typeof nextRunRaw === "string") {
      next_run = nextRunRaw;
    }
    const trig = typeof row.trigger === "string" ? row.trigger : "";
    const enabled = typeof row.enabled === "boolean" ? row.enabled : true;
    const classification =
      typeof row.classification === "string" ? row.classification : "unknown";

    let last_completed_at: string | null | undefined;
    const lcaRaw = row.last_completed_at ?? row.last_run ?? row.lastRun;
    if (typeof lcaRaw === "string" || lcaRaw === null || lcaRaw === undefined) {
      last_completed_at = typeof lcaRaw === "string" ? lcaRaw : lcaRaw === null ? null : undefined;
    }

    let run_count: number | null | undefined;
    const rc = row.run_count ?? row.execution_count ?? row.success_count;
    if (typeof rc === "number" && Number.isFinite(rc)) {
      run_count = rc;
    } else if (rc === null) {
      run_count = null;
    }

    jobs.push({
      id: idRaw.trim(),
      next_run,
      trigger: trig,
      enabled,
      classification,
      ...(last_completed_at !== undefined ? { last_completed_at } : {}),
      ...(run_count !== undefined ? { run_count } : {}),
    });
  }

  return {
    status: "data",
    jobs,
    lastRunExported,
    sourcePath: "/internal/schedulers",
  };
}

export function useBrainSchedulers(): BrainSchedulersFetchState & { retry: () => void } {
  const [state, setState] = useState<BrainSchedulersFetchState>({
    loading: true,
    data: undefined,
    error: null,
  });
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    setState({ loading: true, data: undefined, error: null });
    try {
      const payload = await fetchSchedulersPayload();
      setState({ loading: false, data: payload, error: null });
    } catch (e) {
      setState({
        loading: false,
        data: undefined,
        error: e instanceof Error ? e : new Error("Failed to load Brain schedulers."),
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [tick, load]);

  const retry = useCallback(() => {
    setTick((x) => x + 1);
  }, []);

  return { ...state, retry };
}
