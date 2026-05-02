import Link from "next/link";
import { notFound } from "next/navigation";
import { AlertTriangle, ArrowLeft, Lock } from "lucide-react";

import { createDocMarkdownComponents } from "@/components/admin/docs/doc-markdown";
import { DocKnowledgeRail } from "@/components/admin/docs/doc-knowledge-rail";
import { GithubMarkIcon } from "@/components/github-mark-icon";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { loadDocContent, loadDocsIndex } from "@/lib/docs";
import { computeReadTime } from "@/lib/doc-metadata";

const PWL_DOC_TITLE_PREFIX = "Paperwork Labs ";

function stripPaperworkLabsDocTitle(title: string): string {
  if (title.startsWith(PWL_DOC_TITLE_PREFIX)) {
    return title.slice(PWL_DOC_TITLE_PREFIX.length);
  }
  return title;
}

export const dynamic = "force-static";
export const revalidate = 300;

export function generateStaticParams() {
  const { entries } = loadDocsIndex();
  return entries.map((e) => ({ slug: e.slug }));
}

type Params = Promise<{ slug: string }>;

export default async function DocPage({ params }: { params: Params }) {
  const { slug } = await params;
  const doc = loadDocContent(slug);
  if (!doc) {
    notFound();
  }
  const { entry, markdown, lastModified, wordCount } = doc;
  const isImmutable = entry.category === "philosophy";
  const githubUrl = `https://github.com/paperwork-labs/paperwork/blob/main/${entry.path}`;

  const { entries: indexEntries } = loadDocsIndex();
  const pathToSlug = new Map(indexEntries.map((e) => [e.path, e.slug]));

  const markdownComponents = createDocMarkdownComponents({
    sourcePath: entry.path,
    pathToSlug,
  });

  return (
    <div className="space-y-6">
      <nav className="flex items-center justify-between text-xs text-zinc-500">
        <Link
          href="/admin/docs"
          className="flex items-center gap-1 hover:text-zinc-200"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          All docs
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          {entry.exists ? (
            <Link
              href={`/admin/docs/${entry.slug}/edit`}
              className="rounded-lg bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/25"
            >
              Edit in Studio
            </Link>
          ) : null}
          <a
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 hover:text-zinc-200"
          >
            <GithubMarkIcon className="h-3.5 w-3.5" />
            View on GitHub
          </a>
        </div>
      </nav>

      <header className="space-y-2 rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold text-zinc-100">
            {stripPaperworkLabsDocTitle(entry.title)}
          </h1>
          {isImmutable ? (
            <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
              <Lock className="h-3 w-3" />
              immutable
            </span>
          ) : null}
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
            {entry.category}
          </span>
        </div>
        <p className="text-sm text-zinc-400">{entry.summary}</p>
        <div className="flex flex-wrap gap-2 pt-2 text-[10px]">
          {entry.owners.map((owner) => (
            <span
              key={owner}
              className="rounded-full bg-sky-500/10 px-1.5 py-0.5 font-medium text-sky-300"
            >
              owner: {owner}
            </span>
          ))}
          {entry.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-zinc-400"
            >
              {tag}
            </span>
          ))}
        </div>
        <div className="flex gap-4 pt-2 text-[10px] text-zinc-500">
          <span>
            ~{computeReadTime(wordCount)} min read · {wordCount.toLocaleString()} words
          </span>
          {lastModified ? (
            <span>
              last modified {new Date(lastModified).toLocaleDateString()}
            </span>
          ) : null}
          <span>
            path: <span className="text-zinc-400">{entry.path}</span>
          </span>
        </div>
      </header>

      {!entry.exists ? (
        <div className="flex items-start gap-3 rounded-xl border border-rose-800/40 bg-rose-950/20 p-4 text-sm text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            This doc is listed in <code>docs/_index.yaml</code> but the file is
            missing on disk. Either restore the file or remove the entry from
            the index so agents don&apos;t cite a ghost.
          </div>
        </div>
      ) : null}

      <article className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-6">
        <div className="prose prose-invert prose-zinc max-w-none prose-headings:text-zinc-100 prose-a:text-sky-400 prose-code:text-amber-300 prose-code:before:content-[''] prose-code:after:content-[''] prose-pre:bg-zinc-900/80 prose-pre:overflow-x-auto prose-pre:border prose-pre:border-zinc-800 prose-table:my-6 prose-thead:border-zinc-800 prose-th:border-b prose-th:border-zinc-800 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:text-zinc-300 prose-td:border-b prose-td:border-zinc-900 prose-td:px-3 prose-td:py-2 prose-td:text-zinc-300 prose-tr:border-zinc-800">
          <DocKnowledgeRail
            slug={entry.slug}
            markdownBody={markdown}
            className="float-right ml-6 mb-4 w-72 not-prose hidden lg:block"
          />
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {markdown}
          </ReactMarkdown>
          <div className="clear-both" aria-hidden />
        </div>
      </article>

      <div className="lg:hidden">
        <DocKnowledgeRail slug={entry.slug} markdownBody={markdown} />
      </div>
    </div>
  );
}
