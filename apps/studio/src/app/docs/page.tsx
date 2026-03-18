import fs from "node:fs/promises";
import path from "node:path";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

const DOC_MAP: Record<string, string> = {
  tasks: "docs/TASKS.md",
  knowledge: "docs/KNOWLEDGE.md",
  financials: "docs/FINANCIALS.md",
  masterPlan: "docs/VENTURE_MASTER_PLAN.md",
  readme: "README.md",
};

type DocsPageProps = {
  searchParams: Promise<{ doc?: string }>;
};

export default async function DocsPage({ searchParams }: DocsPageProps) {
  const params = await searchParams;
  const selected = params.doc && DOC_MAP[params.doc] ? params.doc : "tasks";
  const relativePath = DOC_MAP[selected];
  const absolutePath = path.join(process.cwd(), relativePath);
  const markdown = await fs.readFile(absolutePath, "utf8");

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-8 lg:flex-row">
        <aside className="w-full shrink-0 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:w-56">
          <p className="mb-3 text-xs uppercase tracking-wide text-zinc-400">Docs Viewer</p>
          <nav className="space-y-2 text-sm">
            {Object.entries(DOC_MAP).map(([key, file]) => (
              <Link
                key={key}
                href={`/docs?doc=${key}`}
                className={`block rounded-md px-3 py-2 transition ${
                  selected === key
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                }`}
              >
                {file}
              </Link>
            ))}
          </nav>
        </aside>

        <section className="min-w-0 flex-1 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
          <p className="mb-4 text-xs uppercase tracking-wide text-zinc-500">{relativePath}</p>
          <article className="prose prose-invert max-w-none prose-pre:overflow-x-auto">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </article>
        </section>
      </div>
    </main>
  );
}
