#!/usr/bin/env node
/**
 * Evaluates open PRs for agent auto-merge and merges via REST API (squash + delete branch).
 * See docs/infra/PR_PIPELINE_AUTOMATION.md
 */
import { getJson, getRepo, ghJson } from "./lib/github-fetch.mjs";

const SELF_CHECK_SUBSTR = [
  "pr-pipeline-auto-merge",
  "agent auto-merge",
  "auto-merge on approval",
  "auto-merge dependabot",
];

const DEFAULT_BOTS =
  "paperwork-labs[bot],paperwork-labs-bot,github-actions[bot],cursor[bot],paperwork-labs-bot[bot]";

function parseBotLogins() {
  const raw = process.env.AGENT_PR_BOT_LOGINS || DEFAULT_BOTS;
  return new Set(
    raw
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean),
  );
}

const BOT_LOGINS = parseBotLogins();
const PREFIXES = ["feat/", "fix/", "chore/", "brand/", "docs/"];

const BLOCKING = new Set([
  "do-not-merge",
  "needs-founder-review",
  "blocked",
  "wip",
  "hold",
]);

function branchOk(ref) {
  if (!ref) return false;
  return PREFIXES.some((p) => ref.startsWith(p));
}

function isDependabot(login) {
  return login === "dependabot[bot]" || login === "dependabot-preview[bot]";
}

function hasAgentLabel(labels) {
  return (labels || []).some((l) => l.name === "agent-authored");
}

function isEligibleAuthor(pr) {
  const login = pr.user?.login;
  if (!login) return false;
  if (isDependabot(login)) return false;
  if (BOT_LOGINS.has(login)) return true;
  if (hasAgentLabel(pr.labels || [])) return true;
  return false;
}

function isSelfCheckName(name) {
  if (!name) return false;
  const n = name.toLowerCase();
  return SELF_CHECK_SUBSTR.some((s) => n.includes(s.toLowerCase()));
}

const RATE_LIMIT_RE = /rate\s*limit|resource\s*limit|too many requests|build limit|deployment limit|quota exceeded|resource limited|hobby.*limit/i;

async function checkRunOutput(owner, repo, checkRunId, token) {
  const data = await getJson(
    `https://api.github.com/repos/${owner}/${repo}/check-runs/${checkRunId}`,
  );
  const title = data.output?.title || "";
  const summary = data.output?.summary || "";
  const text = data.output?.text || "";
  return `${title}\n${summary}\n${text}`;
}

async function vercelFailureIsSoftPass(owner, repo, token, run) {
  if (!/vercel/i.test(run.name || "")) return false;
  if (run.conclusion !== "failure" && run.conclusion !== "timed_out") return false;
  try {
    const blob = await checkRunOutput(owner, repo, run.id, token);
    return RATE_LIMIT_RE.test(blob);
  } catch {
    return false;
  }
}

async function fetchAllCheckRuns(owner, repo, sha) {
  const runs = [];
  let url = `https://api.github.com/repos/${owner}/${repo}/commits/${sha}/check-runs?per_page=100`;
  const { token } = getRepo();
  for (;;) {
    const res = await fetch(url, {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`check-runs ${res.status} ${t.slice(0, 300)}`);
    }
    const data = await res.json();
    runs.push(...(data.check_runs || []));
    const next = res.headers.get("link")?.match(/<([^>]+)>;\s*rel="next"/);
    if (!next) break;
    url = next[1];
  }
  return runs;
}

async function checksPassForSha(owner, repo, sha, token) {
  const runs = await fetchAllCheckRuns(owner, repo, sha);
  const pending = [];
  const hardFailures = [];

  for (const c of runs) {
    if (isSelfCheckName(c.name)) continue;
    if (c.status !== "completed") {
      pending.push(c.name);
      continue;
    }
    const ok = ["success", "skipped", "neutral", "cancelled"].includes(
      c.conclusion || "",
    );
    if (ok) continue;
    if (await vercelFailureIsSoftPass(owner, repo, token, c)) continue;
    hardFailures.push(`${c.name}=${c.conclusion}`);
  }

  return { ok: pending.length === 0 && hardFailures.length === 0, pending, hardFailures };
}

async function getRequestedReviewers(owner, repo, num) {
  const data = await getJson(
    `https://api.github.com/repos/${owner}/${repo}/pulls/${num}/requested_reviewers`,
  );
  const users = (data.users || []).length;
  const teams = (data.teams || []).length;
  return users + teams;
}

function log(line) {
  process.stdout.write(`${line}\n`);
}

export async function main() {
  const { owner, repo, token } = getRepo();
  if (!token) {
    log("error: GITHUB_TOKEN missing");
    process.exit(1);
  }

  const pulls = await getJson(
    `https://api.github.com/repos/${owner}/${repo}/pulls?state=open&per_page=100&base=main`,
  );

  const summary = [];
  for (const pr of pulls) {
    const num = pr.number;
    if (pr.draft) {
      summary.push(`#${num}: skip — draft`);
      continue;
    }
    if ((pr.base?.ref || "") !== "main") {
      summary.push(`#${num}: skip — base not main`);
      continue;
    }
    if (!isEligibleAuthor(pr)) {
      summary.push(`#${num}: skip — not agent/bot/label`);
      continue;
    }
    if (!branchOk(pr.head?.ref || "")) {
      summary.push(`#${num}: skip — branch prefix`);
      continue;
    }
    const labels = (pr.labels || []).map((l) => l.name);
    const block = labels.find((l) => BLOCKING.has(l));
    if (block) {
      summary.push(`#${num}: skip — label ${block}`);
      continue;
    }
    if (pr.mergeable === false) {
      summary.push(`#${num}: skip — conflicts`);
      continue;
    }
    if (pr.mergeable === null) {
      summary.push(`#${num}: skip — mergeability unknown`);
      continue;
    }

    const rev = await getRequestedReviewers(owner, repo, num);
    if (rev > 0) {
      summary.push(`#${num}: skip — ${rev} pending reviewer(s)`);
      continue;
    }

    const sha = pr.head.sha;
    const { ok, pending, hardFailures } = await checksPassForSha(
      owner,
      repo,
      sha,
      token,
    );
    if (!ok) {
      const detail =
        hardFailures.length > 0
          ? `fail: ${hardFailures.slice(0, 3).join("; ")}`
          : `pending: ${pending.slice(0, 3).join("; ")}`;
      summary.push(`#${num}: skip — ${detail}`);
      continue;
    }

    try {
      await ghJson(`/pulls/${num}/merge`, {
        method: "PUT",
        body: { merge_method: "squash" },
      });
      // delete branch (REST)
      const headRef = pr.head?.ref;
      if (pr.head?.repo?.full_name === `${owner}/${repo}` && headRef) {
        try {
          await ghJson(`/git/refs/heads/${encodeURIComponent(headRef)}`, {
            method: "DELETE",
          });
        } catch (e) {
          summary.push(
            `#${num}: merged (squash) — delete-branch warning: ${e.message}`,
          );
          continue;
        }
      }
      summary.push(`#${num}: merged (squash) + delete-branch`);
    } catch (e) {
      summary.push(`#${num}: error — ${e.message}`);
    }
  }

  const body = summary.join("\n") || "no open PRs";
  log(body);

  if (process.env.GITHUB_OUTPUT) {
    const fs = await import("node:fs");
    fs.appendFileSync(
      process.env.GITHUB_OUTPUT,
      `summary<<EOF\n${body}\nEOF\n`,
    );
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
