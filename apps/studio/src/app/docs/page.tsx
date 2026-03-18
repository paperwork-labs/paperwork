import fs from "node:fs/promises";
import path from "node:path";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

const DOCS = [
  { key: "tasks", label: "Tasks", file: "docs/TASKS.md" },
  { key: "knowledge", label: "Knowledge", file: "docs/KNOWLEDGE.md" },
  { key: "financials", label: "Financials", file: "docs/FINANCIALS.md" },
  { key: "masterPlan", label: "Master Plan", file: "docs/VENTURE_MASTER_PLAN.md" },
  { key: "efin", label: "EFIN Filing Instructions", file: "docs/EFIN_FILING_INSTRUCTIONS.md" },
  { key: "partnerships", label: "Partnerships", file: "docs/PARTNERSHIPS.md" },
  { key: "aiModelRegistry", label: "AI Model Registry", file: "docs/AI_MODEL_REGISTRY.md" },
  { key: "readme", label: "Repository README", file: "README.md" },
] as const;

type DocsPageProps = {
  searchParams: Promise<{ doc?: string }>;
};

async function docExists(relativePath: string) {
  try {
    await fs.access(path.join(process.cwd(), relativePath));
    return true;
  } catch {
    return false;
  }
}

export default async function DocsPage({ searchParams }: DocsPageProps) {
  const params = await searchParams;
  const availableDocs = (
    await Promise.all(
      DOCS.map(async (doc) => ({
        ...doc,
        exists: await docExists(doc.file),
      })),
    )
  ).filter((doc) => doc.exists);
  const defaultDoc = availableDocs.find((doc) => doc.key === "tasks") ?? availableDocs[0];
  const selectedDoc =
    availableDocs.find((doc) => doc.key === params.doc) ??
    defaultDoc ??
    ({ key: "readme", label: "Repository README", file: "README.md" } as const);
  const relativePath = selectedDoc.file;
  const absolutePath = path.join(process.cwd(), relativePath);
  const markdown = await fs.readFile(absolutePath, "utf8");

  return (
    <main id="top" className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-8 lg:flex-row">
        <aside className="w-full shrink-0 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 lg:sticky lg:top-6 lg:h-fit lg:w-64">
          <p className="mb-3 text-xs uppercase tracking-wide text-zinc-400">Docs Viewer</p>
          <nav className="space-y-2 text-sm">
            {availableDocs.map((doc) => (
              <Link
                key={doc.key}
                href={`/docs?doc=${doc.key}`}
                className={`block rounded-md px-3 py-2 transition ${
                  selectedDoc.key === doc.key
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                }`}
              >
                {doc.label}
                <span className="ml-2 text-xs text-zinc-500">{doc.file}</span>
              </Link>
            ))}
          </nav>
        </aside>

        <section className="min-w-0 flex-1 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
          <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">
            <Link href="/docs" className="hover:text-zinc-300">
              Docs
            </Link>{" "}
            / {selectedDoc.label}
          </p>
          <p className="mb-4 text-xs uppercase tracking-wide text-zinc-600">{relativePath}</p>
          <article className="prose prose-invert max-w-none prose-pre:overflow-x-auto">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </article>
        </section>
      </div>
      <div className="pointer-events-none fixed bottom-6 right-6">
        <Link
          href="#top"
          className="pointer-events-auto rounded-full border border-zinc-700 bg-zinc-900/80 px-4 py-2 text-xs uppercase tracking-wide text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
        >
          Top
        </Link>
      </div>
    </main>
  );
}
