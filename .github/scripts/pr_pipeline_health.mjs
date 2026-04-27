#!/usr/bin/env node
/**
 * Nightly PR pipeline metrics for .github/workflows/pr-pipeline-health.yaml
 * Uses GitHub REST + fetch (Node 20+). Writes $GITHUB_STEP_SUMMARY.
 */
import fs from "node:fs";
import path from "node:path";

const repoFull = process.env.GITHUB_REPOSITORY;
const token = process.env.GITHUB_TOKEN;
const mainRef = process.env.MAIN_REF || "main";

if (!repoFull || !token) {
  console.error("GITHUB_REPOSITORY and GITHUB_TOKEN are required");
  process.exit(1);
}

const [owner, repo] = repoFull.split("/");

const SELF_CHECKS = new Set([
  "auto-merge",
  "sweep",
  "Auto-merge dependabot sweep",
  "agent-pr-merge",
  "Auto-merge GREEN agent PRs",
  "merge-green-agent-prs",
  "PR triage",
  "pr-triage",
  "Auto-rebase open PRs on main",
]);

const BLOCKING = new Set([
  "blocked",
  "do-not-merge",
  "wip",
  "hold",
  "needs-review",
  "needs-founder-review",
  "draft",
]);

function parseAllowlist(raw) {
  const bots = [];
  const users = [];
  let section = null;
  for (const line of raw.split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    if (t === "bots:") {
      section = "bots";
      continue;
    }
    if (t === "users:") {
      section = "users";
      continue;
    }
    const m = t.match(/^-\s*(.+)$/);
    if (!m || !section) continue;
    const v = m[1].trim().replace(/^['"]|['"]$/g, "");
    if (section === "bots") bots.push(v);
    if (section === "users") users.push(v);
  }
  return { bots, users };
}

function isAllowlisted(login, allow) {
  return allow.bots.includes(login) || allow.users.includes(login);
}

function isDependabot(login) {
  return login === "dependabot[bot]" || login === "dependabot-preview[bot]";
}

async function ghApi(pth, { query, method = "GET", body } = {}) {
  const u = new URL(`https://api.github.com${pth}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) u.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(u, {
    method,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`GitHub ${pth} ${res.status}: ${text.slice(0, 300)}`);
  }
  return text ? JSON.parse(text) : null;
}

async function listAllOpenPrs() {
  const all = [];
  for (let page = 1; page <= 5; page++) {
    const batch = await ghApi(`/repos/${owner}/${repo}/pulls`, {
      query: { state: "open", per_page: 100, page },
    });
    if (!batch.length) break;
    all.push(...batch);
  }
  return all;
}

async function isIgnorableVercelFailure(checkRun) {
  const name = (checkRun.name || "").toLowerCase();
  if (!name.includes("vercel")) return false;
  let blob = "";
  try {
    const full = await ghApi(`/repos/${owner}/${repo}/check-runs/${checkRun.id}`);
    blob = `${full.output?.title || ""} ${full.output?.summary || ""} ${full.output?.text || ""}`.toLowerCase();
  } catch {
    blob = "";
  }
  return /(rate limit|build limit exceeded|deployment skipped|too many requests|skipped deployment|builds are paused)/.test(
    blob
  );
}

async function checksReady(sha) {
  const { check_runs: checkRuns = [] } = await ghApi(`/repos/${owner}/${repo}/commits/${sha}/check-runs`, {
    query: { per_page: 100 },
  });
  for (const c of checkRuns) {
    if (SELF_CHECKS.has(c.name)) continue;
    if (c.status === "completed" && ["success", "skipped", "neutral"].includes(c.conclusion || "")) {
      continue;
    }
    if (c.status === "completed" && c.conclusion === "failure") {
      if (await isIgnorableVercelFailure(c)) continue;
    }
    return { ok: false, sample: c };
  }
  return { ok: true, sample: null };
}

const workspace = process.env.GITHUB_WORKSPACE || process.cwd();
const allowPath = path.join(workspace, ".github", "auto-merge-allowlist.yaml");
const allow = parseAllowlist(fs.readFileSync(allowPath, "utf8"));

const prs = await listAllOpenPrs();
let behindMain = 0;
let prsWithFailingOrPendingCi = 0;
let readyButAutomationGap = 0;
const gapExamples = [];
let blockingCount = 0;

for (const stub of prs) {
  const pr = await ghApi(`/repos/${owner}/${repo}/pulls/${stub.number}`);

  const labels = (pr.labels || []).map((l) => l.name);
  if (labels.some((l) => BLOCKING.has(l))) {
    blockingCount += 1;
  }

  const headSha = pr.head?.sha;
  if (!headSha) continue;
  let behindVal = 0;
  let haveCompare = false;
  try {
    const cmp = await ghApi(
      `/repos/${owner}/${repo}/compare/${encodeURIComponent(`${mainRef}...${headSha}`)}`
    );
    behindVal = Number(cmp.behind_by) || 0;
    haveCompare = true;
  } catch {
    haveCompare = false;
  }
  if (haveCompare && behindVal > 0) behindMain += 1;

  const { ok: ciOk } = await checksReady(headSha);
  if (!ciOk) prsWithFailingOrPendingCi += 1;

  const author = pr.user?.login || "";
  const isSweepCandidate =
    isDependabot(author) ||
    (isAllowlisted(author, allow) && !isDependabot(author));
  const hasHardBlock = labels.some((l) =>
    ["blocked", "do-not-merge", "wip", "hold"].includes(l)
  );
  const ageMs = Date.now() - new Date(pr.created_at).getTime();
  const allowlistTooYoung =
    isAllowlisted(author, allow) && !isDependabot(author) && ageMs < 5 * 60 * 1000;
  const allowlistTooLarge =
    isAllowlisted(author, allow) && !isDependabot(author) && (pr.additions ?? 0) > 800;

  const upToDate = haveCompare && behindVal === 0;
  const mergeable = pr.mergeable === true;
  if (
    isSweepCandidate &&
    !hasHardBlock &&
    !allowlistTooYoung &&
    !allowlistTooLarge &&
    mergeable &&
    upToDate &&
    ciOk &&
    !pr.draft
  ) {
    // Automation should be able to merge (subject to branch protection / budgets)
    readyButAutomationGap += 1;
    if (gapExamples.length < 8) {
      gapExamples.push(
        `#${pr.number} @${author} (+${pr.additions ?? 0} lines)`
      );
    }
  }
}

const lines = [
  "## PR pipeline health",
  "",
  `Default branch: \`${mainRef}\` (compare for “behind” metrics)`,
  "",
  "| Metric | Count |",
  "| --- | ---: |",
  `| Open PRs | ${prs.length} |`,
  `| Behind \`${mainRef}\` (merge base) | ${behindMain} |`,
  `| Failing or pending non-Vercel-soft checks (approx.) | ${prsWithFailingOrPendingCi} |`,
  `| Has blocking / hold / review-hold label | ${blockingCount} |`,
  `| **Open PRs that look auto-merge-eligible (bot/allowlist, green, up to date, mergeable)** | ${readyButAutomationGap} |`,
  "",
];

if (readyButAutomationGap > 0) {
  lines.push(
    "> **Automation gap (non-zero):** dependabot/allowlist PRs with green checks and up to date, still open. Review branch protection, sweep logs, or merge budget.",
    ""
  );
  for (const g of gapExamples) {
    lines.push(`- ${g}`);
  }
  if (readyButAutomationGap > gapExamples.length) {
    lines.push(`- _… and ${readyButAutomationGap - gapExamples.length} more_`);
  }
} else {
  lines.push("**Automation gap:** 0 (no bot/allowlist PRs stuck green + mergeable + up to date).");
}

const summary = lines.join("\n");
console.log(summary);
const out = process.env.GITHUB_STEP_SUMMARY;
if (out) {
  await fs.promises.appendFile(out, summary + "\n");
}
