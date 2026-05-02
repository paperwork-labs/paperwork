"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast, Toaster } from "sonner";

import { createDocMarkdownComponents } from "@/components/admin/docs/doc-markdown";
import { MarkdownEditor } from "@/components/admin/MarkdownEditor";
import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";
import { HqPageContainer } from "@/components/admin/hq/HqPageContainer";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import type { DocEntry } from "@/lib/docs";
import { loadDocsIndex } from "@/lib/docs";
import {
  composeStudioDocFile,
  splitDocRaw,
  validateStudioDocFrontmatter,
} from "@/lib/doc-frontmatter-validation";

export type DocEditClientProps = {
  slug: string;
  initialRaw: string;
  entry: DocEntry;
  githubTokenConfigured: boolean;
};

export function DocEditClient({
  slug,
  initialRaw,
  entry,
  githubTokenConfigured,
}: DocEditClientProps) {
  const router = useRouter();
  const splitInitial = useMemo(() => splitDocRaw(initialRaw), [initialRaw]);
  const [frontmatterYaml, setFrontmatterYaml] = useState(splitInitial.front);
  const [bodyMd, setBodyMd] = useState(splitInitial.body);
  const [commitMessage, setCommitMessage] = useState(`docs(${slug}): update content`);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const fm = useMemo(
    () => validateStudioDocFrontmatter(frontmatterYaml),
    [frontmatterYaml],
  );

  const fullFilePreview = useMemo(
    () => composeStudioDocFile(frontmatterYaml, bodyMd),
    [frontmatterYaml, bodyMd],
  );

  const previewBodyMd = bodyMd.trim() ? bodyMd : "*Nothing to preview yet.*";

  const markdownComponents = useMemo(() => {
    const { entries } = loadDocsIndex();
    const pathToSlug = new Map(entries.map((e) => [e.path, e.slug]));
    return createDocMarkdownComponents({
      sourcePath: entry.path,
      pathToSlug,
    });
  }, [entry.path]);

  async function handleSaveAsPr() {
    setSaveError(null);
    if (!fm.canSave) {
      setSaveError("Fix frontmatter warnings before saving.");
      toast.error("Frontmatter incomplete");
      return;
    }
    if (!githubTokenConfigured) {
      setSaveError("GITHUB_TOKEN is not configured in this environment.");
      toast.error("GitHub token missing");
      return;
    }
    setSaving(true);
    try {
      const composed = composeStudioDocFile(frontmatterYaml, bodyMd);
      const res = await fetch("/api/admin/docs/save-as-pr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slug,
          content: composed,
          commitMessage: commitMessage.trim() || `docs(${slug}): update content`,
        }),
      });
      const json = (await res.json()) as {
        success?: boolean;
        error?: string;
        prUrl?: string;
        message?: string;
      };
      if (json.error === "MISSING_GITHUB_TOKEN") {
        toast.error(json.message ?? "GitHub token missing");
        setSaveError(json.message ?? "GITHUB_TOKEN is not configured.");
        return;
      }
      if (!res.ok || !json.success || !json.prUrl) {
        const err = json.message ?? json.error ?? `Save failed (${res.status})`;
        setSaveError(err);
        toast.error(err);
        return;
      }
      toast.success("Pull request opened");
      window.open(json.prUrl, "_blank", "noopener,noreferrer");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unexpected error";
      setSaveError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div data-testid="admin-doc-editor-root" className="space-y-6 pb-16">
      <HqPageContainer variant="wide">
        <HqPageHeader
          eyebrow="Documentation"
          title={`Edit · ${entry.title}`}
          subtitle={`Path: ${entry.path} · Changes open as a GitHub PR; main is never written directly.`}
          breadcrumbs={[
            { label: "Docs", href: "/admin/docs" },
            { label: entry.title, href: `/admin/docs/${slug}` },
            { label: "Edit" },
          ]}
          actions={
            <>
              <Link
                href={`/admin/docs/${slug}`}
                className="inline-flex rounded-lg border border-border bg-muted/40 px-3 py-1.5 text-sm font-medium text-muted-foreground transition hover:bg-muted/60 hover:text-foreground"
              >
                Cancel
              </Link>
              <button
                type="button"
                disabled={saving || !fm.canSave}
                onClick={() => void handleSaveAsPr()}
                className="inline-flex rounded-lg bg-emerald-500/20 px-3 py-1.5 text-sm font-semibold text-emerald-200 ring-1 ring-emerald-500/40 transition hover:bg-emerald-500/25 disabled:pointer-events-none disabled:opacity-40"
              >
                {saving ? "Opening PR…" : "Save as PR"}
              </button>
            </>
          }
        />

        {!githubTokenConfigured ? (
          <div className="mb-6">
            <HqMissingCredCard
              service="GitHub"
              envVar="GITHUB_TOKEN"
              docsLink="https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/PR_PIPELINE_AUTOMATION.md"
              description="Saving as a PR needs GITHUB_TOKEN with repo and pull-requests permissions in this deployment."
            />
          </div>
        ) : null}

        {fm.warnings.length > 0 ? (
          <div
            className="mb-4 rounded-lg border border-amber-800/50 bg-amber-950/25 px-3 py-2 text-sm text-amber-100"
            data-testid="admin-doc-editor-frontmatter-warnings"
          >
            <p className="font-medium text-amber-200">Frontmatter</p>
            <ul className="mt-1 list-inside list-disc text-amber-100/90">
              {fm.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
            {!fm.canSave ? (
              <p className="mt-2 text-xs text-amber-200/90">
                Save as PR is disabled until required fields are present.
              </p>
            ) : null}
          </div>
        ) : null}

        {saveError ? (
          <p className="mb-4 rounded-lg border border-rose-800/60 bg-rose-950/30 px-3 py-2 text-sm text-rose-100">
            {saveError}
          </p>
        ) : null}

        <label className="block space-y-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Commit message
          <input
            value={commitMessage}
            onChange={(e) => setCommitMessage(e.target.value)}
            className="block w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm font-normal normal-case tracking-normal text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-zinc-600"
          />
        </label>

        <label className="mt-6 block space-y-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Frontmatter <span className="font-normal lowercase text-zinc-600">(YAML)</span>
          <textarea
            value={frontmatterYaml}
            onChange={(e) => setFrontmatterYaml(e.target.value)}
            rows={10}
            spellCheck={false}
            data-testid="admin-doc-editor-frontmatter"
            className="block w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs normal-case tracking-normal text-zinc-200 outline-none focus:border-zinc-600"
          />
        </label>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="min-w-0 space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Editor
            </p>
            <MarkdownEditor value={bodyMd} onChange={setBodyMd} />
          </div>
          <div className="min-w-0 space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Live preview
            </p>
            <div className="markdown-preview-pane max-h-[min(70vh,640px)] overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
              <div className="prose prose-invert prose-sm max-w-none text-zinc-200 prose-headings:text-zinc-50 prose-a:text-sky-400 prose-code:text-amber-300 prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {previewBodyMd}
                </ReactMarkdown>
              </div>
            </div>
            <details className="rounded-lg border border-zinc-800/80 bg-zinc-900/30 text-xs text-zinc-500">
              <summary className="cursor-pointer px-3 py-2 text-zinc-400">
                Full file (with frontmatter)
              </summary>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap border-t border-zinc-800/80 p-3 font-mono text-[11px] text-zinc-500">
                {fullFilePreview}
              </pre>
            </details>
          </div>
        </div>

        <p className="mt-10 text-xs text-zinc-600">
          <button
            type="button"
            className="text-sky-400 underline-offset-4 hover:underline"
            onClick={() => router.push(`/admin/docs/${slug}`)}
          >
            Back to doc view
          </button>
        </p>

        <Toaster richColors theme="dark" position="bottom-right" />
      </HqPageContainer>
    </div>
  );
}
