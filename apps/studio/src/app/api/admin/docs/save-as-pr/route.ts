import { NextResponse } from "next/server";
import { Octokit } from "@octokit/rest";
import { z } from "zod";

import { findDocBySlug } from "@/lib/docs";

export const runtime = "nodejs";

const BodySchema = z.object({
  slug: z.string().min(1),
  content: z.string(),
  commitMessage: z.string().min(1).max(500),
});

function resolveRepoEnv(): { owner: string; repo: string } {
  const full =
    process.env.STUDIO_GITHUB_REPO?.trim() ||
    process.env.GITHUB_REPO?.trim() ||
    "paperwork-labs/paperwork";
  const [owner, repo] = full.split("/");
  if (!owner?.length || !repo?.length) {
    throw new Error("Invalid repository env (owner/repo)");
  }
  return { owner, repo: repo.trim() };
}

function makePrBody(slug: string): string {
  return [
    `Suggested update from Studio \`/admin/docs/${slug}/edit\`.`,
    "",
    "## Checklist",
    "",
    "- [ ] Frontmatter complete (owner, last_reviewed, doc_kind, domain, status)",
    "- [ ] Content reads correctly in GitHub preview",
    "- [ ] No accidental secret or token paste",
    "",
    "---",
    "",
    "**Not done** — complete the checklist before merging.",
    "",
  ].join("\n");
}

function safeBranchSlug(slug: string): string {
  const sanitized = slug.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 40);
  return sanitized || "doc";
}

export async function POST(request: Request) {
  const token = process.env.GITHUB_TOKEN?.trim();
  if (!token) {
    return NextResponse.json(
      {
        success: false,
        error: "MISSING_GITHUB_TOKEN",
        message:
          "GITHUB_TOKEN is not set in this environment. Add a token with repo scope, redeploy, then try again.",
      },
      { status: 503 },
    );
  }

  let parsedBody: unknown;
  try {
    parsedBody = await request.json();
  } catch {
    return NextResponse.json({ success: false, error: "INVALID_JSON" }, { status: 400 });
  }

  const parsed = BodySchema.safeParse(parsedBody);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: "INVALID_BODY" }, { status: 400 });
  }

  const { slug, content, commitMessage } = parsed.data;
  const entry = findDocBySlug(slug);
  if (!entry) {
    return NextResponse.json({ success: false, error: "UNKNOWN_SLUG" }, { status: 404 });
  }

  const relPath = entry.path.replace(/^\/+/, "");
  if (!relPath.startsWith("docs/") || !relPath.endsWith(".md") || relPath.includes("..")) {
    return NextResponse.json({ success: false, error: "UNSUPPORTED_PATH" }, { status: 400 });
  }

  let owner: string;
  let repo: string;
  try {
    ({ owner, repo } = resolveRepoEnv());
  } catch (e) {
    return NextResponse.json(
      {
        success: false,
        error: "BAD_REPO_ENV",
        message: e instanceof Error ? e.message : "Repository configuration invalid",
      },
      { status: 500 },
    );
  }

  const octokit = new Octokit({ auth: token });
  const branch = `studio-doc-${safeBranchSlug(slug)}-${Date.now().toString(36)}`;

  try {
    const mainRef = await octokit.rest.git.getRef({
      owner,
      repo,
      ref: "heads/main",
    });
    const mainSha = mainRef.data.object.sha;

    await octokit.rest.git.createRef({
      owner,
      repo,
      ref: `refs/heads/${branch}`,
      sha: mainSha,
    });

    let fileSha: string | undefined;
    try {
      const { data: fileData } = await octokit.rest.repos.getContent({
        owner,
        repo,
        path: relPath,
        ref: branch,
      });
      if (
        !Array.isArray(fileData) &&
        fileData.type === "file" &&
        typeof fileData.sha === "string"
      ) {
        fileSha = fileData.sha;
      }
    } catch {
      fileSha = undefined;
    }

    await octokit.rest.repos.createOrUpdateFileContents({
      owner,
      repo,
      path: relPath,
      message: commitMessage,
      content: Buffer.from(content, "utf-8").toString("base64"),
      branch,
      sha: fileSha,
    });

    const pr = await octokit.rest.pulls.create({
      owner,
      repo,
      title: `[docs] ${entry.title}`,
      body: makePrBody(slug),
      head: branch,
      base: "main",
    });

    return NextResponse.json({
      success: true,
      prUrl: pr.data.html_url,
      branch,
    });
  } catch (e) {
    const message =
      e && typeof e === "object" && "message" in e
        ? String((e as { message?: string }).message)
        : "GitHub API error";

    console.error("[save-as-pr]", { slug, relPath, message });

    const statusHint =
      /Bad credentials/i.test(message) || /Unauthorized/i.test(message) ? 403 : 502;

    return NextResponse.json(
      {
        success: false,
        error: "GITHUB_API_ERROR",
        message,
      },
      { status: statusHint },
    );
  }
}
