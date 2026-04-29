/**
 * Workstreams board — single source of truth for the prioritized list of
 * Q2 (and beyond) tech-debt and product workstreams.
 *
 * The JSON file `apps/studio/src/data/workstreams.json` is the canonical
 * data; this module is the canonical schema + helpers.
 *
 * Read order:
 *   1. UI (`/admin/workstreams` page) loads + parses + renders + reorders
 *   2. Brain dispatcher (`workstream_dispatcher.py`) reads top-N every 30 min
 *   3. Brain progress (`workstream_progress.py`) recomputes `percent_done`
 *      hourly from merged-PR `brief_tag` matches
 *
 * Contract details live in `docs/infra/WORKSTREAMS_BOARD.md`.
 */

import { z } from "zod";

const instantParseOk = z.string().refine((s) => !Number.isNaN(Date.parse(s)), {
  message: "Expected parseable ISO-8601 timestamp",
});

/** ISO-8601 datetime; normalizes date-only ``YYYY-MM-DD`` to midnight UTC (Brain / EA edits). */
function zDateTimeLoose() {
  return z.preprocess(
    (v) => {
      if (v === null || v === undefined) return v;
      if (typeof v !== "string") return v;
      const s = v.trim();
      if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return `${s}T00:00:00.000Z`;
      return s;
    },
    instantParseOk,
  );
}

function zDateTimeLooseNullable() {
  return z.preprocess(
    (v) => {
      if (v === null || v === undefined) return v;
      if (typeof v !== "string") return v;
      const s = v.trim();
      if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return `${s}T00:00:00.000Z`;
      return s;
    },
    z.union([z.null(), instantParseOk]),
  );
}

export const WorkstreamStatusSchema = z.enum([
  "pending",
  "in_progress",
  "blocked",
  "completed",
  "cancelled",
]);

export const WorkstreamOwnerSchema = z.enum([
  "brain",
  "founder",
  "opus",
]);

const ID_RE = /^WS-\d{2,3}-[a-z0-9-]+$/;
const TRACK_RE = /^[A-Z][0-9A-Z]{0,2}$/;
const BRIEF_TAG_RE = /^track:[a-z0-9-]+$/;

export const WorkstreamSchema = z.object({
  id: z
    .string()
    .regex(ID_RE, "id must match WS-<NN>-<kebab-slug>"),
  title: z.string().min(3).max(100),
  track: z
    .string()
    .regex(TRACK_RE, "track must be uppercase letter optionally followed by 1-2 digits/letters"),
  priority: z.number().int().nonnegative(),
  status: WorkstreamStatusSchema,
  percent_done: z.number().int().min(0).max(100),
  owner: WorkstreamOwnerSchema,
  brief_tag: z.string().regex(BRIEF_TAG_RE, "brief_tag must be 'track:<kebab-slug>'"),
  blockers: z.array(z.string().min(3)).default([]),
  last_pr: z.number().int().positive().nullable(),
  last_activity: zDateTimeLoose(),
  last_dispatched_at: zDateTimeLooseNullable(),
  notes: z.string().max(500).default(""),
  estimated_pr_count: z.number().int().positive().nullable().default(null),
  github_actions_workflow: z.string().nullable().default(null),
  related_plan: z.string().nullable().default(null),
  updated_at: z.string().datetime().nullable().optional(),
  override_percent: z.number().int().min(0).max(100).nullable().optional(),
  derived_percent: z.number().int().min(0).max(100).nullable().optional(),
  pr_url: z.string().nullable().optional(),
  prs: z.array(z.number().int().positive()).nullable().optional(),
  pr_numbers: z.array(z.number().int().positive()).nullable().optional(),
});

const WorkstreamsFileBaseSchema = z.object({
  version: z.literal(1),
  updated: z.string().datetime(),
  workstreams: z.array(WorkstreamSchema),
});

function _refineWorkstreamsFile(
  file: z.infer<typeof WorkstreamsFileBaseSchema>,
  ctx: z.RefinementCtx,
) {
  const ids = file.workstreams.map((w) => w.id);
  const idSet = new Set(ids);
  if (idSet.size !== ids.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Workstream ids must be unique",
      path: ["workstreams"],
    });
  }
  const priorities = file.workstreams.map((w) => w.priority);
  const prioritySet = new Set(priorities);
  if (prioritySet.size !== priorities.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message:
        "Workstream priorities must be unique — drag-reorder relies on stable ordering",
      path: ["workstreams"],
    });
  }
  for (const ws of file.workstreams) {
    if (ws.status === "completed" && ws.percent_done !== 100) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${ws.id}: completed status requires percent_done=100 (got ${ws.percent_done})`,
        path: ["workstreams"],
      });
    }
    if (ws.status === "blocked" && ws.blockers.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${ws.id}: blocked status requires at least one entry in blockers[]`,
        path: ["workstreams"],
      });
    }
    if (ws.status === "cancelled" && ws.percent_done !== 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${ws.id}: cancelled status requires percent_done=0 (got ${ws.percent_done})`,
        path: ["workstreams"],
      });
    }
  }
}

export const WorkstreamsFileSchema =
  WorkstreamsFileBaseSchema.superRefine(_refineWorkstreamsFile);

export const WorkstreamsBoardBrainEnvelopeSchema = WorkstreamsFileBaseSchema.extend({
  generated_at: z.string(),
  source: z.enum(["brain-writeback", "bundled-json-fallback"]),
  ttl_seconds: z.number().int().nonnegative(),
  writeback_last_run_at: z.string().datetime().nullable(),
}).superRefine(_refineWorkstreamsFile);

export type Workstream = z.infer<typeof WorkstreamSchema>;
export type WorkstreamsFile = z.infer<typeof WorkstreamsFileSchema>;
export type WorkstreamStatus = z.infer<typeof WorkstreamStatusSchema>;
export type WorkstreamOwner = z.infer<typeof WorkstreamOwnerSchema>;

/**
 * Brain dispatch contract — pick the next N workstreams a cheap subagent
 * should run. Honoured by `apis/brain/app/schedulers/workstream_dispatcher.py`.
 *
 *   1. owner === "brain"            (founder/opus tasks need humans)
 *   2. status in {pending, in_progress}
 *   3. blockers is empty
 *   4. last_dispatched_at older than DISPATCH_COOLDOWN_MS
 *   5. sort ascending by `priority`, take first N
 */
export const DISPATCH_COOLDOWN_MS = 4 * 60 * 60 * 1000;

export function dispatchableWorkstreams(
  file: WorkstreamsFile,
  n = 3,
  now: number = Date.now(),
): Workstream[] {
  return file.workstreams
    .filter((w) => w.owner === "brain")
    .filter((w) => w.status === "pending" || w.status === "in_progress")
    .filter((w) => w.blockers.length === 0)
    .filter((w) => {
      if (!w.last_dispatched_at) return true;
      return now - new Date(w.last_dispatched_at).getTime() > DISPATCH_COOLDOWN_MS;
    })
    .sort((a, b) => a.priority - b.priority)
    .slice(0, n);
}

/**
 * KPIs summarised at the top of the board.
 */
export interface WorkstreamKpis {
  total: number;
  active: number;
  pending: number;
  blocked: number;
  completed: number;
  cancelled: number;
  avg_percent_done: number;
}

export function computeKpis(file: WorkstreamsFile): WorkstreamKpis {
  const total = file.workstreams.length;
  const active = file.workstreams.filter((w) => w.status === "in_progress").length;
  const pending = file.workstreams.filter((w) => w.status === "pending").length;
  const blocked = file.workstreams.filter((w) => w.status === "blocked").length;
  const completed = file.workstreams.filter((w) => w.status === "completed").length;
  const cancelled = file.workstreams.filter((w) => w.status === "cancelled").length;
  const forAvg = file.workstreams.filter(
    (w) => w.status === "pending" || w.status === "in_progress",
  );
  const avg_percent_done =
    forAvg.length === 0
      ? 0
      : Math.round(forAvg.reduce((acc, w) => acc + w.percent_done, 0) / forAvg.length);
  return { total, active, pending, blocked, completed, cancelled, avg_percent_done };
}
