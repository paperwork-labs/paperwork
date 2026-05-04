/**
 * Static operator hints for ingesting Cursor agent-transcripts into Brain.
 * Auth env names match `brain-client.ts` / `brain-admin-proxy.ts` and
 * `scripts/backfill-transcripts.ts`.
 */
export function TranscriptsOperatorPanel() {
  return (
    <section
      className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
      aria-labelledby="transcripts-operator-heading"
    >
      <h2
        id="transcripts-operator-heading"
        className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400"
      >
        Operator
      </h2>
      <p className="text-sm text-zinc-400">
        This page reads transcripts already stored in Brain. To backfill from Cursor{" "}
        <span className="font-mono text-xs text-zinc-300">agent-transcripts/*.jsonl</span>{" "}
        on your machine, run the repo script from the monorepo root:
      </p>
      <pre className="mt-3 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950/80 p-3 font-mono text-xs text-zinc-200">
        pnpm run backfill:transcripts
      </pre>
      <p className="mt-3 text-sm text-zinc-400">
        <span className="font-medium text-zinc-300">Environment (local CLI)</span> — the script
        expects{" "}
        <code className="rounded bg-zinc-950/80 px-1 py-0.5 font-mono text-[11px] text-zinc-200">
          BRAIN_API_URL
        </code>{" "}
        (Brain base URL; script appends{" "}
        <code className="font-mono text-[11px] text-zinc-200">/api/v1</code> when needed) and{" "}
        <code className="rounded bg-zinc-950/80 px-1 py-0.5 font-mono text-[11px] text-zinc-200">
          BRAIN_API_SECRET
        </code>{" "}
        (sent as{" "}
        <code className="font-mono text-[11px] text-zinc-200">X-Brain-Secret</code> on admin
        routes — same header Studio uses when proxying Brain per{" "}
        <code className="font-mono text-[11px] text-zinc-200">brain-admin-proxy.ts</code>
        ). Optional:{" "}
        <code className="rounded bg-zinc-950/80 px-1 py-0.5 font-mono text-[11px] text-zinc-200">
          TRANSCRIPT_ROOT
        </code>{" "}
        or <span className="font-mono text-xs text-zinc-300">--root &lt;dir&gt;</span> to override
        the default transcript directory; use{" "}
        <span className="font-mono text-xs text-zinc-300">--dry-run</span> to list files without
        calling the API.
      </p>
      <p className="mt-3 text-xs text-zinc-500">
        Brain also exposes{" "}
        <code className="font-mono text-[11px] text-zinc-400">POST .../admin/transcripts/ingest-batch</code>{" "}
        for directory scans on the <span className="text-zinc-400">Brain server filesystem</span>{" "}
        only — not wired in Studio here (Vercel has no access to your laptop paths).
      </p>
    </section>
  );
}
