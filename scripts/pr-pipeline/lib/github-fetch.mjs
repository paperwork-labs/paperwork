/**
 * Minimal GitHub REST helpers for pr-pipeline scripts (Node 20+).
 * Uses GITHUB_TOKEN and GITHUB_REPOSITORY (owner/repo).
 */

export function getRepo() {
  const full = process.env.GITHUB_REPOSITORY || "";
  const [owner, repo] = full.split("/");
  if (!owner || !repo) {
    throw new Error("GITHUB_REPOSITORY is not set");
  }
  return { owner, repo, token: process.env.GITHUB_TOKEN || "" };
}

export async function ghJson(path, { method = "GET", body } = {}) {
  const { owner, repo, token } = getRepo();
  if (!token) throw new Error("GITHUB_TOKEN is not set");
  const url =
    path.startsWith("https://")
      ? path
      : `https://api.github.com/repos/${owner}/${repo}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`GitHub ${method} ${url}: ${res.status} ${t.slice(0, 500)}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function getJson(url) {
  const { token } = getRepo();
  if (!token) throw new Error("GITHUB_TOKEN is not set");
  const res = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`GET ${url}: ${res.status} ${t.slice(0, 500)}`);
  }
  return res.json();
}

/** Paginate GET /path starting after ? or &. */
export async function paginate(path) {
  const all = [];
  let url = `https://api.github.com/repos/${getRepo().owner}/${getRepo().repo}${path.startsWith("/") ? path : `/${path}`}`;
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
      throw new Error(`GET ${url}: ${res.status} ${t.slice(0, 500)}`);
    }
    const page = await res.json();
    if (Array.isArray(page)) {
      all.push(...page);
    } else {
      all.push(page);
    }
    const next = res.headers.get("link")?.match(/<([^>]+)>;\s*rel="next"/);
    if (!next) break;
    url = next[1];
  }
  return all;
}
