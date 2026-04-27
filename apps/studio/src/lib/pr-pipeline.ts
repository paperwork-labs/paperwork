/**
 * GitHub data for /admin/pr-pipeline — uses GITHUB_TOKEN server-side only.
 */
import { unstable_cache } from "next/cache";

const REPO = "paperwork-labs/paperwork";
const API = "https://api.github.com";

type GqlCheck = {
  status: string;
  conclusion: string | null;
  name: string;
};

export type PipelinePrRow = {
  number: number;
  title: string;
  html_url: string;
  author: string;
  labels: string[];
  mergeable_state: string | null;
  draft: boolean;
  /** Heuristic bucket for the dashboard */
  bucket: "green" | "yellow" | "red";
  /** Human-readable reason for yellow/red */
  note: string;
};

export type WorkflowRunRow = {
  id: number;
  name: string;
  conclusion: string | null;
  created_at: string;
  html_url: string;
  event: string;
};

function authHeaders(): HeadersInit {
  const token = process.env.GITHUB_TOKEN?.trim();
  if (!token) {
    throw new Error("GITHUB_TOKEN is not configured");
  }
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`GitHub ${res.status}: ${t.slice(0, 400)}`);
  }
  return res.json() as Promise<T>;
}

async function listOpenPulls(): Promise<
  {
    number: number;
    title: string;
    html_url: string;
    draft: boolean;
    user: { login?: string };
    labels: { name: string }[];
    head: { sha: string };
    mergeable: boolean | null;
    mergeable_state: string | null;
  }[]
> {
  const out = [];
  let page = 1;
  for (;;) {
    const part = await getJson<
      {
        number: number;
        title: string;
        html_url: string;
        draft: boolean;
        user: { login?: string };
        labels: { name: string }[];
        head: { sha: string };
        mergeable: boolean | null;
        mergeable_state: string | null;
      }[]
    >(`${API}/repos/${REPO}/pulls?state=open&per_page=100&page=${page}&base=main&sort=updated`);
    if (part.length === 0) break;
    out.push(...part);
    if (part.length < 100) break;
    page += 1;
  }
  return out;
}

async function headCheckSummary(sha: string): Promise<{
  fail: number;
  pending: number;
  vercelFailSoft: number;
}> {
  const data = await getJson<{ check_runs: GqlCheck[] }>(
    `${API}/repos/${REPO}/commits/${sha}/check-runs?per_page=100`,
  );
  const runs = data.check_runs || [];
  let fail = 0;
  let pending = 0;
  let vercelFailSoft = 0;
  for (const c of runs) {
    if (/pr-pipeline-auto-merge/i.test(c.name)) continue;
    if (c.status !== "completed") {
      pending += 1;
      continue;
    }
    if (["success", "skipped", "neutral", "cancelled"].includes(c.conclusion || "")) continue;
    if (/vercel/i.test(c.name)) {
      vercelFailSoft += 1;
      continue;
    }
    fail += 1;
  }
  return { fail, pending, vercelFailSoft };
}

function bucketFor(
  pr: {
    draft: boolean;
    labels: { name: string }[];
    mergeable_state: string | null;
    mergeable: boolean | null;
  },
  checks: { fail: number; pending: number; vercelFailSoft: number },
): { bucket: PipelinePrRow["bucket"]; note: string } {
  const labels = new Set(pr.labels.map((l) => l.name));
  if (labels.has("do-not-merge") || labels.has("needs-founder-review")) {
    return { bucket: "yellow", note: "blocked by label" };
  }
  if (pr.draft) {
    return { bucket: "yellow", note: "draft" };
  }
  if (pr.mergeable_state === "dirty" || pr.mergeable === false) {
    return { bucket: "red", note: "merge conflict or not mergeable" };
  }
  if (checks.pending > 0) {
    return { bucket: "yellow", note: `${checks.pending} check(s) pending` };
  }
  if (checks.fail > 0) {
    return { bucket: "red", note: `${checks.fail} failing check(s)` };
  }
  if (checks.vercelFailSoft > 0) {
    return {
      bucket: "green",
      note: `Vercel noise only (${checks.vercelFailSoft}) — merge policy may still allow`,
    };
  }
  if (pr.mergeable_state === "clean" || pr.mergeable === true) {
    return { bucket: "green", note: "CI clean" };
  }
  return { bucket: "yellow", note: "unknown merge / check state" };
}

export async function loadPrPipelineDashboard() {
  if (!process.env.GITHUB_TOKEN?.trim()) {
    return {
      pulls: [] as PipelinePrRow[],
      mergeRuns: [] as WorkflowRunRow[],
      rebaseRuns: [] as WorkflowRunRow[],
      stuck: [] as { number: number; title: string; html_url: string; author: string; labels: string[] }[],
      fetchedAt: new Date().toISOString(),
      error: "GITHUB_TOKEN is not set — add a token in Vercel/Render to enable live data.",
    };
  }
  const [
    pulls,
    mergeRuns,
    rebaseRuns,
    stuck,
  ] = await Promise.all([
    listOpenPulls(),
    listRecentWorkflowRuns("pr-pipeline-auto-merge.yaml"),
    listRecentWorkflowRuns("pr-pipeline-auto-rebase-on-main.yaml"),
    listStuckIssues(),
  ]);

  const rows: PipelinePrRow[] = [];
  for (const p of pulls) {
    const checks = await headCheckSummary(p.head.sha);
    const { bucket, note } = bucketFor(p, checks);
    rows.push({
      number: p.number,
      title: p.title,
      html_url: p.html_url,
      author: p.user?.login ?? "?",
      labels: p.labels.map((l) => l.name),
      mergeable_state: p.mergeable_state,
      draft: p.draft,
      bucket,
      note,
    });
  }

  return {
    pulls: rows,
    mergeRuns,
    rebaseRuns,
    stuck: stuck.map((i) => ({
      number: i.number,
      title: i.title,
      html_url: i.html_url,
      author: i.user?.login ?? "?",
      labels: i.labels.map((l) => l.name),
    })),
    fetchedAt: new Date().toISOString(),
    error: null,
  };
}

async function listRecentWorkflowRuns(workflowFile: string): Promise<WorkflowRunRow[]> {
  const wf = await getJson<{ id: number }>(`${API}/repos/${REPO}/actions/workflows/${workflowFile}`);
  const data = await getJson<{
    workflow_runs: {
      id: number;
      name: string;
      conclusion: string | null;
      created_at: string;
      html_url: string;
      event: string;
    }[];
  }>(`${API}/repos/${REPO}/actions/workflows/${wf.id}/runs?per_page=30`);
  const since = Date.now() - 24 * 3600 * 1000;
  return (data.workflow_runs || [])
    .filter((r) => Date.parse(r.created_at) >= since)
    .map((r) => ({
      id: r.id,
      name: r.name,
      conclusion: r.conclusion,
      created_at: r.created_at,
      html_url: r.html_url,
      event: r.event,
    }));
}

async function listStuckIssues() {
  const data = await getJson<
    {
      number: number;
      title: string;
      html_url: string;
      user: { login?: string };
      labels: { name: string }[];
      created_at: string;
      pull_request?: unknown;
    }[]
  >(
    `${API}/repos/${REPO}/issues?labels=pr-pipeline-escalated&state=open&per_page=50`,
  );
  return data.filter((i) => i.pull_request);
}

export const getPrPipelineDashboardCached = unstable_cache(
  loadPrPipelineDashboard,
  ["pr-pipeline-dashboard", REPO],
  { revalidate: 60 },
);
