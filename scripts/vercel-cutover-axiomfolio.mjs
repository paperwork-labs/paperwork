#!/usr/bin/env node
/**
 * One-off helper for legacy `axiomfolio` → Next.js metadata + prod deploy before domains move to `axiomfolio-next`.
 * Default: dry-run (prints planned Vercel API calls). Use `--apply` to execute.
 *
 * Requires: VERCEL_API_TOKEN (team scope). Optional: GITHUB_TOKEN for higher GitHub API rate limits when resolving main SHA.
 */

const TEAM_ID = "team_RwfzJ9ySyLuVcoWdKJfXC7h5";
const LEGACY_PROJECT_ID = "prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE";
const NEXT_PROJECT_ID = "prj_z3JVQGLLfsJO2QZJnK5BvMjfFoK3";
const GITHUB_REPO_ID = 1175885030;

const PATCH_BODY = {
  framework: "nextjs",
  rootDirectory: "apps/axiomfolio",
  buildCommand: "pnpm --filter @paperwork-labs/axiomfolio... run build",
  installCommand:
    "cd ../.. && corepack enable && corepack prepare pnpm@10.32.1 --activate && rm -rf node_modules/.pnpm && pnpm install --frozen-lockfile --filter=@paperwork-labs/axiomfolio...",
  outputDirectory: ".next",
  nodeVersion: "22.x",
};

const VERCEL_ORIGIN = "https://api.vercel.com";

function projectUrl() {
  return `${VERCEL_ORIGIN}/v9/projects/${encodeURIComponent(LEGACY_PROJECT_ID)}?teamId=${encodeURIComponent(TEAM_ID)}`;
}

function deploymentsUrl() {
  return `${VERCEL_ORIGIN}/v13/deployments?teamId=${encodeURIComponent(TEAM_ID)}`;
}

function deploymentByIdUrl(id) {
  return `${VERCEL_ORIGIN}/v13/deployments/${encodeURIComponent(id)}?teamId=${encodeURIComponent(TEAM_ID)}`;
}

/**
 * @param {boolean} apply
 * @param {string} method
 * @param {string} url
 * @param {number | string} codeOrDash
 */
function logLine(apply, method, url, codeOrDash) {
  const mode = apply ? "apply" : "dry";
  console.log(`[${mode}] ${method} ${url} -> ${codeOrDash}`);
}

async function resolveMainSha() {
  const url = "https://api.github.com/repos/paperwork-labs/paperwork/commits/main";
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "paperworklabs-vercel-cutover-axiomfolio",
    ...(process.env.GITHUB_TOKEN
      ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` }
      : {}),
  };
  const res = await fetch(url, { headers });
  const code = res.status;
  console.log(`[meta] GET ${url} -> ${code}`);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Failed to resolve main SHA via GitHub API (${code}): ${t.slice(0, 400)}`);
  }
  const data = await res.json();
  const sha = data.sha;
  if (!sha || typeof sha !== "string") {
    throw new Error("GitHub API response missing commits/main sha");
  }
  return sha;
}

async function vercelReq(apply, token, method, url, body) {
  /** @type {RequestInit} */
  const init = {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(method !== "GET" && body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    ...(body !== undefined && method !== "GET" ? { body: JSON.stringify(body) } : {}),
  };
  const res = await fetch(url, init);
  const code = res.status;
  logLine(apply, method, url, code);
  const text = await res.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { _raw: text };
  }
  return { ok: res.ok, code, json, text };
}

async function main() {
  const apply = process.argv.includes("--apply");
  const token = process.env.VERCEL_API_TOKEN;
  if (!token || String(token).trim() === "") {
    console.error("error: VERCEL_API_TOKEN is required (export from Vercel → Settings → Tokens).");
    process.exit(1);
  }

  console.error(
    `Canonical Next.js project id (dashboard): ${NEXT_PROJECT_ID} — this script targets legacy ${LEGACY_PROJECT_ID} for PATCH + deploy fallback.`,
  );

  const mainSha = await resolveMainSha();
  console.error(`Resolved github main SHA: ${mainSha}`);

  if (!apply) {
    logLine(false, "GET", projectUrl(), "—");
    console.error(
      "  → If framework !== nextjs: PATCH project with Next.js root/build/install/output/nodeVersion (see PATCH_BODY in script).",
    );
    logLine(false, "PATCH", projectUrl(), "—");
    console.error(`  → PATCH body: ${JSON.stringify(PATCH_BODY)}`);
    logLine(false, "POST", deploymentsUrl(), "—");
    console.error(
      `  → POST body: ${JSON.stringify(
        {
          target: "production",
          gitSource: {
            type: "github",
            ref: "main",
            sha: mainSha,
            repoId: GITHUB_REPO_ID,
          },
          project: LEGACY_PROJECT_ID,
          name: "axiomfolio",
        },
        null,
        2,
      )}`,
    );
    console.error(
      "  → Then poll GET /v13/deployments/{id} every 30s × 15 (READY → exit 0; ERROR/CANCELED → exit 1).",
    );
    console.error("Dry-run complete — pass --apply to execute the above against the Vercel API.");
    process.exit(0);
  }

  // --- apply ---
  const getRes = await vercelReq(true, token, "GET", projectUrl());
  if (!getRes.ok) {
    console.error(getRes.text.slice(0, 2000));
    process.exit(1);
  }

  const fw = getRes.json?.framework;
  let patched = false;
  if (fw === "nextjs") {
    console.error(`Step A: framework is already nextjs — skipping PATCH.`);
  } else {
    console.error(`Step A: framework=${JSON.stringify(fw)} — PATCH → nextjs`);
    const patchRes = await vercelReq(true, token, "PATCH", projectUrl(), PATCH_BODY);
    if (!patchRes.ok) {
      console.error(patchRes.text.slice(0, 2000));
      process.exit(1);
    }
    patched = true;
  }
  if (patched) {
    console.error("Legacy project metadata updated.");
  }

  console.error("Step B: trigger production deployment");
  const postBody = {
    target: "production",
    gitSource: {
      type: "github",
      ref: "main",
      sha: mainSha,
      repoId: GITHUB_REPO_ID,
    },
    project: LEGACY_PROJECT_ID,
    name: "axiomfolio",
  };
  const postRes = await vercelReq(true, token, "POST", deploymentsUrl(), postBody);
  if (!postRes.ok) {
    console.error(postRes.text.slice(0, 2000));
    process.exit(1);
  }

  const deployId = postRes.json?.id ?? postRes.json?.uid;
  if (!deployId || typeof deployId !== "string") {
    console.error("Unexpected deployment response (missing id):", JSON.stringify(postRes.json).slice(0, 1500));
    process.exit(1);
  }
  console.error(`Deployment id: ${deployId}`);

  console.error("Step C: poll deployment state");
  for (let attempt = 1; attempt <= 15; attempt++) {
    const pollUrl = deploymentByIdUrl(deployId);
    const pollRes = await vercelReq(true, token, "GET", pollUrl);
    if (!pollRes.ok) {
      console.error(pollRes.text.slice(0, 2000));
      process.exit(1);
    }
    const state = pollRes.json?.readyState ?? pollRes.json?.state ?? "?";
    console.error(`  attempt ${attempt}/15: state=${state}`);
    if (state === "READY") {
      process.exit(0);
    }
    if (state === "ERROR" || state === "CANCELED") {
      process.exit(1);
    }
    if (attempt < 15) {
      await new Promise((r) => setTimeout(r, 30_000));
    }
  }
  console.error("Timeout waiting for READY after 15 × 30s.");
  process.exit(1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
