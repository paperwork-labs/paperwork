#!/usr/bin/env node
/**
 * Seed Brain SQL `Goal → Epic → Sprint → Task` rows for WS-82 (Studio HQ overhaul).
 *
 * Env:
 *   BRAIN_API_URL — e.g. https://brain.example.com (with or without trailing `/`; `/api/v1` is appended)
 *   BRAIN_API_SECRET — `X-Brain-Secret` for admin routes
 *   WS82_SEED_OWNER_SLUG — optional epic/task owner (default: `founder`)
 *
 * Run: `pnpm seed:epics` or `pnpm exec tsx scripts/seed-epic-hierarchy.ts`
 *
 * Idempotency: stable primary keys; POST then PATCH on HTTP 409.
 */

type BrainEnvelope<T> = {
  success: boolean;
  data?: T;
  error?: string | null;
};

const GH_PR = (n: number) => `https://github.com/paperwork-labs/paperwork/pull/${n}`;

const GOAL_ID = "goal-ship-studio-hq-q2-2026";
const EPIC_ID = "epic-ws-82-studio-hq";

const GOAL_WRITTEN_AT = "2026-05-02T00:00:00.000Z";

function sanitizeEnv(val: string | undefined): string {
  if (!val) return "";
  return val.trim().replace(/\\n$/, "").replace(/\/+$/, "");
}

/** Match `apps/studio/src/lib/brain-admin-proxy.ts` — admin routes under `/api/v1`. */
function brainApiV1Root(): string | null {
  const raw = sanitizeEnv(process.env.BRAIN_API_URL);
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

function die(msg: string): never {
  console.error(msg);
  process.exit(1);
}

async function brainFetch(
  root: string,
  secret: string,
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  const url = `${root}${path}`;
  const headers: Record<string, string> = { "X-Brain-Secret": secret };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
}

async function parseEnvelope<T>(label: string, res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${label}: HTTP ${res.status} ${text.slice(0, 600)}`);
  }
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`${label}: response is not JSON`);
  }
  const env = json as BrainEnvelope<T>;
  if (typeof env === "object" && env !== null && "success" in env) {
    if (!env.success) {
      throw new Error(`${label}: ${env.error ?? "success=false"}`);
    }
    if (env.data !== undefined) {
      return env.data as T;
    }
  }
  return json as T;
}

async function postOrPatchJson<T>(
  root: string,
  secret: string,
  label: string,
  postPath: string,
  patchPath: string,
  createBody: unknown,
  patchBody: unknown,
): Promise<T> {
  const postRes = await brainFetch(root, secret, "POST", postPath, createBody);
  if (postRes.status === 409) {
    const patchRes = await brainFetch(root, secret, "PATCH", patchPath, patchBody);
    return parseEnvelope<T>(`${label} (patch)`, patchRes);
  }
  return parseEnvelope<T>(`${label} (create)`, postRes);
}

type WaveDef = {
  id: string;
  title: string;
  status: string;
  ordinal: number;
  tasks: { id: string; title: string; status: string; githubPr: number }[];
};

const WAVES: WaveDef[] = [
  {
    id: "sprint-ws-82-wave-0",
    title: "Stop the bleed",
    status: "shipped",
    ordinal: 0,
    tasks: [
      { id: "task-ws-82-pr-598", title: "PR-0a Vercel narrow cuts", status: "merged", githubPr: 598 },
      { id: "task-ws-82-pr-600", title: "PR-0b Hetzner bootstrap", status: "merged", githubPr: 600 },
      { id: "task-ws-82-pr-601", title: "PR-2a Brain employees table", status: "merged", githubPr: 601 },
      { id: "task-ws-82-pr-599", title: "PR-3a Brain epic hierarchy", status: "merged", githubPr: 599 },
    ],
  },
  {
    id: "sprint-ws-82-wave-1",
    title: "Studio UI foundations",
    status: "shipped",
    ordinal: 1,
    tasks: [
      { id: "task-ws-82-pr-603", title: "PR-2c People org grid", status: "merged", githubPr: 603 },
      { id: "task-ws-82-pr-604", title: "PR-3b Epics tree view", status: "merged", githubPr: 604 },
      { id: "task-ws-82-pr-602", title: "PR-6a Doc viewer fixes", status: "merged", githubPr: 602 },
    ],
  },
  {
    id: "sprint-ws-82-wave-2",
    title: "CRUD + Products + Infra",
    status: "shipped",
    ordinal: 2,
    tasks: [
      { id: "task-ws-82-pr-607", title: "PR-3c CRUD modals", status: "merged", githubPr: 607 },
      { id: "task-ws-82-pr-606", title: "PR-4a Product hub", status: "merged", githubPr: 606 },
      { id: "task-ws-82-pr-605", title: "PR-5a Hetzner infra panel", status: "merged", githubPr: 605 },
    ],
  },
  {
    id: "sprint-ws-82-wave-3",
    title: "Conversations + Docs + CI",
    status: "shipped",
    ordinal: 3,
    tasks: [
      { id: "task-ws-82-pr-608", title: "PR-0d Vercel prebuilt", status: "merged", githubPr: 608 },
      { id: "task-ws-82-pr-609", title: "PR-5b Conversations persona reply", status: "merged", githubPr: 609 },
      { id: "task-ws-82-pr-610", title: "PR-7a Runbook reorg", status: "merged", githubPr: 610 },
    ],
  },
  {
    id: "sprint-ws-82-wave-4",
    title: "Sync + Paths + Ingest",
    status: "shipped",
    ordinal: 4,
    tasks: [
      { id: "task-ws-82-pr-611", title: "PR-8a Employee sync script", status: "merged", githubPr: 611 },
      { id: "task-ws-82-pr-614", title: "PR-8b Reading paths fix", status: "merged", githubPr: 614 },
      { id: "task-ws-82-pr-613", title: "PR-9a Transcript ingest", status: "merged", githubPr: 613 },
    ],
  },
  {
    id: "sprint-ws-82-wave-5",
    title: "Profiles + Dashboard + Render",
    status: "in_progress",
    ordinal: 5,
    tasks: [
      { id: "task-ws-82-pr-615", title: "PR-8c Brain Render upgrade", status: "in_progress", githubPr: 615 },
      { id: "task-ws-82-pr-616", title: "PR-2d Employee profiles", status: "merged", githubPr: 616 },
      { id: "task-ws-82-pr-617", title: "PR-10a Overview dashboard", status: "merged", githubPr: 617 },
    ],
  },
  {
    id: "sprint-ws-82-wave-6",
    title: "Design tokens + nav polish",
    status: "shipped",
    ordinal: 6,
    tasks: [
      { id: "task-ws-82-pr-618", title: "PR-11a Design system tokens + StatusDot/StatusBadge", status: "merged", githubPr: 618 },
      { id: "task-ws-82-pr-619", title: "PR-12a Seed epic hierarchy script", status: "merged", githubPr: 619 },
    ],
  },
  {
    id: "sprint-ws-82-wave-7",
    title: "Brain status + sidebar + teams",
    status: "shipped",
    ordinal: 7,
    tasks: [
      { id: "task-ws-82-pr-620", title: "Global Brain status banner", status: "merged", githubPr: 620 },
      { id: "task-ws-82-pr-621", title: "Admin nav sidebar polish", status: "merged", githubPr: 621 },
      { id: "task-ws-82-pr-622", title: "Seed Brain employees from persona specs", status: "merged", githubPr: 622 },
      { id: "task-ws-82-pr-623", title: "Circles (Teams) page", status: "merged", githubPr: 623 },
    ],
  },
  {
    id: "sprint-ws-82-wave-8",
    title: "Brain dispatch + command palette",
    status: "shipped",
    ordinal: 8,
    tasks: [
      { id: "task-ws-82-pr-624", title: "Dispatcher uses DB epics", status: "merged", githubPr: 624 },
      { id: "task-ws-82-pr-625", title: "Command palette + keyboard shortcuts", status: "merged", githubPr: 625 },
      { id: "task-ws-82-pr-626", title: "Wire Products to Brain DB", status: "merged", githubPr: 626 },
    ],
  },
  {
    id: "sprint-ws-82-wave-9",
    title: "Naming ceremony + infra + overview",
    status: "shipped",
    ordinal: 9,
    tasks: [
      { id: "task-ws-82-pr-627", title: "Naming ceremony trigger", status: "merged", githubPr: 627 },
      { id: "task-ws-82-pr-628", title: "Honest infrastructure status model", status: "merged", githubPr: 628 },
      { id: "task-ws-82-pr-629", title: "Overview dashboard live Brain pulse", status: "merged", githubPr: 629 },
    ],
  },
  {
    id: "sprint-ws-82-wave-10",
    title: "Product hub + conversations + backfill",
    status: "shipped",
    ordinal: 10,
    tasks: [
      { id: "task-ws-82-pr-630", title: "Product hub with live data tabs", status: "merged", githubPr: 630 },
      { id: "task-ws-82-pr-631", title: "Conversation persona reply wired to Brain", status: "merged", githubPr: 631 },
      { id: "task-ws-82-pr-632", title: "Transcript backfill script", status: "merged", githubPr: 632 },
    ],
  },
  {
    id: "sprint-ws-82-wave-11",
    title: "Employee activity + epics search + fixes",
    status: "shipped",
    ordinal: 11,
    tasks: [
      { id: "task-ws-82-pr-633", title: "Employee activity timeline", status: "merged", githubPr: 633 },
      { id: "task-ws-82-pr-634", title: "Epics tree search + filter", status: "merged", githubPr: 634 },
      { id: "task-ws-82-pr-635", title: "Fix Alembic revision duplicate + CI guard", status: "merged", githubPr: 635 },
      { id: "task-ws-82-pr-636", title: "Stop Vercel double-build", status: "merged", githubPr: 636 },
      { id: "task-ws-82-pr-637", title: "Rename Hetzner boxes", status: "merged", githubPr: 637 },
    ],
  },
  {
    id: "sprint-ws-82-wave-12",
    title: "Seed expansion + OKR routes + epic API hardening",
    status: "shipped",
    ordinal: 12,
    tasks: [
      { id: "task-ws-82-pr-638", title: "feat: expand WS-82 seed with Waves 6-11", status: "merged", githubPr: 638 },
      { id: "task-ws-82-pr-639", title: "fix(brain): rename OKR goals routes to /okr/goals", status: "merged", githubPr: 639 },
      { id: "task-ws-82-pr-641", title: "fix(brain): serialize datetimes in epic hierarchy responses + harden stats", status: "merged", githubPr: 641 },
    ],
  },
];

async function main(): Promise<void> {
  const root = brainApiV1Root();
  const secret = sanitizeEnv(process.env.BRAIN_API_SECRET);
  const owner = sanitizeEnv(process.env.WS82_SEED_OWNER_SLUG) || "founder";

  if (!root) {
    die("error: BRAIN_API_URL is not set (or is empty); cannot reach Brain admin API.");
  }
  if (!secret) {
    die("error: BRAIN_API_SECRET is not set (or is empty); admin mutations require X-Brain-Secret.");
  }

  const goalCreate = {
    id: GOAL_ID,
    objective: "Ship Studio as Company HQ",
    horizon: "Q2-2026",
    metric: "HQ command-surface adoption",
    target: "Studio is canonical ops + Brain surface for the company",
    status: "active",
    owner_employee_slug: owner,
    written_at: GOAL_WRITTEN_AT,
    metadata: { seed: "ws-82-pr12a", kind: "okr_goal" },
  };
  const goalPatch = {
    objective: goalCreate.objective,
    horizon: goalCreate.horizon,
    metric: goalCreate.metric,
    target: goalCreate.target,
    status: goalCreate.status,
    owner_employee_slug: goalCreate.owner_employee_slug,
    written_at: goalCreate.written_at,
    metadata: goalCreate.metadata,
  };

  const epicCreate = {
    id: EPIC_ID,
    title: "WS-82 Studio HQ Complete Overhaul",
    goal_id: GOAL_ID,
    product_slug: "studio",
    owner_employee_slug: owner,
    status: "in_progress",
    priority: 1,
    percent_done: 95,
    brief_tag: "studio",
    description: null as string | null,
    related_plan: null as string | null,
    blockers: [] as unknown[],
    metadata: { seed: "ws-82-pr12a", workstream: "WS-82" },
  };
  const epicPatch = {
    title: epicCreate.title,
    goal_id: epicCreate.goal_id,
    product_slug: epicCreate.product_slug,
    owner_employee_slug: epicCreate.owner_employee_slug,
    status: epicCreate.status,
    priority: epicCreate.priority,
    percent_done: epicCreate.percent_done,
    brief_tag: epicCreate.brief_tag,
    description: epicCreate.description,
    related_plan: epicCreate.related_plan,
    blockers: epicCreate.blockers,
    metadata: epicCreate.metadata,
  };

  try {
    await postOrPatchJson(
      root,
      secret,
      "goal",
      "/admin/goals",
      `/admin/goals/${encodeURIComponent(GOAL_ID)}`,
      goalCreate,
      goalPatch,
    );
    console.log(`goal ${GOAL_ID}: ok`);
  } catch (e) {
    die(`error: Brain API unreachable or rejected goal — ${e instanceof Error ? e.message : String(e)}`);
  }

  try {
    await postOrPatchJson(
      root,
      secret,
      "epic",
      "/admin/epics",
      `/admin/epics/${encodeURIComponent(EPIC_ID)}`,
      epicCreate,
      epicPatch,
    );
    console.log(`epic ${EPIC_ID}: ok`);
  } catch (e) {
    die(`error: Brain API unreachable or rejected epic — ${e instanceof Error ? e.message : String(e)}`);
  }

  for (const wave of WAVES) {
    const sprintCreate = {
      id: wave.id,
      epic_id: EPIC_ID,
      title: wave.title,
      goal: null as string | null,
      status: wave.status,
      ordinal: wave.ordinal,
      metadata: { seed: "ws-82-pr12a", wave: wave.ordinal },
    };
    const sprintPatch = {
      title: sprintCreate.title,
      goal: sprintCreate.goal,
      status: sprintCreate.status,
      ordinal: sprintCreate.ordinal,
      metadata: sprintCreate.metadata,
    };
    try {
      await postOrPatchJson(
        root,
        secret,
        `sprint ${wave.id}`,
        "/admin/sprints",
        `/admin/sprints/${encodeURIComponent(wave.id)}`,
        sprintCreate,
        sprintPatch,
      );
      console.log(`sprint ${wave.id}: ok`);
    } catch (e) {
      die(
        `error: Brain API unreachable or rejected sprint ${wave.id} — ${e instanceof Error ? e.message : String(e)}`,
      );
    }

    for (let i = 0; i < wave.tasks.length; i++) {
      const t = wave.tasks[i];
      const prUrl = GH_PR(t.githubPr);
      const taskCreate = {
        id: t.id,
        title: t.title,
        status: t.status,
        sprint_id: wave.id,
        epic_id: EPIC_ID,
        github_pr: t.githubPr,
        github_pr_url: prUrl,
        owner_employee_slug: owner,
        ordinal: i,
        metadata: { seed: "ws-82-pr12a", github_pr_url: prUrl },
      };
      const taskPatch = {
        title: taskCreate.title,
        status: taskCreate.status,
        sprint_id: taskCreate.sprint_id,
        epic_id: taskCreate.epic_id,
        github_pr: taskCreate.github_pr,
        github_pr_url: taskCreate.github_pr_url,
        owner_employee_slug: taskCreate.owner_employee_slug,
        ordinal: taskCreate.ordinal,
        metadata: taskCreate.metadata,
      };
      try {
        await postOrPatchJson(
          root,
          secret,
          `task ${t.id}`,
          "/admin/tasks",
          `/admin/tasks/${encodeURIComponent(t.id)}`,
          taskCreate,
          taskPatch,
        );
        console.log(`task ${t.id}: ok`);
      } catch (e) {
        die(
          `error: Brain API unreachable or rejected task ${t.id} — ${e instanceof Error ? e.message : String(e)}`,
        );
      }
    }
  }

  console.log("seed-epic-hierarchy: complete");
}

main().catch((e) => {
  die(`error: ${e instanceof Error ? e.message : String(e)}`);
});
