#!/usr/bin/env node
/**
 * Pings the founder on PRs that are blocked, dirty, or need review.
 * Skips if a pr-pipeline escalation comment was posted recently.
 */
import { getJson, getRepo, ghJson } from "./lib/github-fetch.mjs";

const MARKER = "<!-- pr-pipeline-escalation v1 -->";
const RATE_LIMIT_RE =
  /rate\s*limit|resource\s*limit|too many requests|build limit|deployment limit|quota exceeded|resource limited|hobby.*limit/i;

const founder = process.env.FOUNDER_GITHUB_LOGIN?.trim() || "sankalp404";
const COOLDOWN_H = parseFloat(process.env.ESCALATION_COMMENT_COOLDOWN_H || "24");

function hoursAgo(iso) {
  if (!iso) return Infinity;
  return (Date.now() - Date.parse(iso)) / 3600000;
}

async function fetchAllCheckRuns(owner, repo, sha) {
  const { token } = getRepo();
  const runs = [];
  let url = `https://api.github.com/repos/${owner}/${repo}/commits/${sha}/check-runs?per_page=100`;
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
      throw new Error(`check-runs ${res.status} ${t.slice(0, 200)}`);
    }
    const data = await res.json();
    runs.push(...(data.check_runs || []));
    const next = res.headers.get("link")?.match(/<([^>]+)>;\s*rel="next"/);
    if (!next) break;
    url = next[1];
  }
  return runs;
}

async function checkRunOutput(owner, repo, id) {
  const data = await getJson(
    `https://api.github.com/repos/${owner}/${repo}/check-runs/${id}`,
  );
  return `${data.output?.title || ""}\n${data.output?.summary || ""}\n${data.output?.text || ""}`;
}

async function isVercelRateLimitFailure(owner, repo, run) {
  if (!/vercel/i.test(run.name || "")) return false;
  if (run.conclusion !== "failure" && run.conclusion !== "timed_out")
    return false;
  try {
    const text = await checkRunOutput(owner, repo, run.id);
    return RATE_LIMIT_RE.test(text);
  } catch {
    return false;
  }
}

/** True if a non-spurious check failed, with failure older than `minH` hours. */
async function hasLongRunningHardFailure(owner, repo, headSha, minH) {
  const runs = await fetchAllCheckRuns(owner, repo, headSha);
  for (const c of runs) {
    if (c.status !== "completed") continue;
    if (["success", "skipped", "neutral", "cancelled"].includes(c.conclusion || ""))
      continue;
    if (await isVercelRateLimitFailure(owner, repo, c)) continue;
    if (hoursAgo(c.completed_at) >= minH) return { yes: true, name: c.name, conclusion: c.conclusion };
  }
  return { yes: false };
}

async function recentEscalationExists(owner, repo, num) {
  const data = await getJson(
    `https://api.github.com/repos/${owner}/${repo}/issues/${num}/comments?per_page=30&sort=created&direction=desc`,
  );
  for (const c of data || []) {
    const b = c.body || "";
    if (!b.includes(MARKER)) continue;
    if (hoursAgo(c.created_at) < COOLDOWN_H) return true;
  }
  return false;
}

async function listOpenPulls(owner, repo) {
  const all = [];
  let page = 1;
  for (;;) {
    const part = await getJson(
      `https://api.github.com/repos/${owner}/${repo}/pulls?state=open&per_page=100&page=${page}&base=main`,
    );
    if (!Array.isArray(part) || part.length === 0) break;
    all.push(...part);
    if (part.length < 100) break;
    page += 1;
  }
  return all;
}

function labelNames(labels) {
  return new Set((labels || []).map((l) => l.name));
}

export async function main() {
  const { owner, repo, token } = getRepo();
  if (!token) {
    console.error("GITHUB_TOKEN missing");
    process.exit(1);
  }

  const pulls = await listOpenPulls(owner, repo);
  const log = [];

  for (const stub of pulls) {
    const num = stub.number;
    const pr = await getJson(
      `https://api.github.com/repos/${owner}/${repo}/pulls/${num}`,
    );
    if ((pr.base?.ref || "") !== "main") continue;

    const labels = labelNames(pr.labels);
    if (await recentEscalationExists(owner, repo, num)) {
      log.push(`#${num}: skip — escalation cooldown`);
      continue;
    }

    let reason = null;

    if (labels.has("needs-founder-review")) {
      reason = "label `needs-founder-review`";
    } else {
      const ms = pr.mergeable_state;
      if (ms === "dirty" && hoursAgo(pr.updated_at) >= 6) {
        reason = "mergeable_state dirty (≈6h+ since last update)";
      } else if (pr.mergeable === false && hoursAgo(pr.updated_at) >= 6) {
        reason = "not mergeable for 6h+ (conflicts or complex)";
      }
    }

    if (!reason) {
      const { yes, name, conclusion } = await hasLongRunningHardFailure(
        owner,
        repo,
        pr.head.sha,
        4,
      );
      if (yes) reason = `CI failure (${name}=${conclusion}, >4h on head)`;
    }

    if (!reason) {
      log.push(`#${num}: ok`);
      continue;
    }

    const body = `${MARKER}\n@${founder} — **PR #${num}** needs attention: ${reason}`;

    await ghJson(`/issues/${num}/comments`, {
      method: "POST",
      body: { body },
    });

    try {
      await ghJson(`/issues/${num}/labels`, {
        method: "POST",
        body: { labels: ["pr-pipeline-escalated"] },
      });
    } catch {
      // label may not exist in repo — ignore
    }
    log.push(`#${num}: escalated — ${reason}`);
  }

  const text = log.join("\n");
  process.stdout.write(`${text}\n`);
  if (process.env.GITHUB_OUTPUT) {
    const fs = await import("node:fs");
    fs.appendFileSync(
      process.env.GITHUB_OUTPUT,
      `summary<<EOF\n${text}\nEOF\n`,
    );
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
