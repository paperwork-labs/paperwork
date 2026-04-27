import Link from "next/link";
import { GitBranch, GitPullRequest, AlertTriangle, Activity } from "lucide-react";

import { getPrPipelineDashboardCached } from "@/lib/pr-pipeline";

export const dynamic = "force-dynamic";

function badge(bucket: "green" | "yellow" | "red") {
  const map = {
    green: "border-emerald-500/50 bg-emerald-950/40 text-emerald-200",
    yellow: "border-amber-500/50 bg-amber-950/40 text-amber-200",
    red: "border-rose-500/50 bg-rose-950/40 text-rose-200",
  } as const;
  const label = { green: "Green", yellow: "Yellow", red: "Red" }[bucket];
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${map[bucket]}`}
    >
      {label}
    </span>
  );
}

export default async function PrPipelinePage() {
  const data = await getPrPipelineDashboardCached();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">PR pipeline</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Agent auto-merge, auto-rebase, and stuck-PR triage. Cached ~60s on the
          server; refresh the page to reload.
        </p>
        {data.fetchedAt ? (
          <p className="mt-1 font-mono text-xs text-zinc-600">Fetched {data.fetchedAt}</p>
        ) : null}
        {data.error ? (
          <p className="mt-3 rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
            {data.error}
          </p>
        ) : null}
      </div>

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          <GitPullRequest className="h-4 w-4" />
          Open pull requests
        </h2>
        <p className="text-xs text-zinc-500">
          Green ≈ auto-mergeable under policy; yellow ≈ action needed; red ≈
          blocked.
        </p>
        <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/50 text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-3 py-2">PR</th>
                <th className="px-3 py-2">State</th>
                <th className="px-3 py-2">Author</th>
                <th className="px-3 py-2">Labels</th>
                <th className="px-3 py-2">Merge</th>
                <th className="px-3 py-2">Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/80 text-zinc-300">
              {data.pulls.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-zinc-500">
                    No open PRs to main (or missing token).
                  </td>
                </tr>
              ) : (
                data.pulls.map((row) => (
                  <tr key={row.number} className="hover:bg-zinc-900/30">
                    <td className="px-3 py-2">
                      <a
                        href={row.html_url}
                        className="font-mono text-sky-400 hover:underline"
                        target="_blank"
                        rel="noreferrer"
                      >
                        #{row.number}
                      </a>{" "}
                      <span className="text-zinc-500">{row.title}</span>
                    </td>
                    <td className="px-3 py-2">{badge(row.bucket)}</td>
                    <td className="px-3 py-2 text-zinc-400">{row.author}</td>
                    <td className="px-3 py-2 text-xs text-zinc-500">
                      {row.labels.length ? row.labels.join(", ") : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-zinc-500">
                      {row.mergeable_state ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-zinc-500">{row.note}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-zinc-500">
            <Activity className="h-4 w-4" />
            Auto-merge runs (24h)
          </h2>
          <ul className="space-y-1.5 text-sm text-zinc-400">
            {data.mergeRuns.length === 0 ? (
              <li className="text-zinc-600">No runs in the last 24 hours.</li>
            ) : (
              data.mergeRuns.map((r) => (
                <li key={r.id}>
                  <a
                    href={r.html_url}
                    className="text-sky-400 hover:underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {r.conclusion ?? "in progress"} · {r.name}
                  </a>
                  <span className="ml-2 text-xs text-zinc-600">
                    {new Date(r.created_at).toLocaleString()}
                  </span>
                </li>
              ))
            )}
          </ul>
        </section>
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-zinc-500">
            <GitBranch className="h-4 w-4" />
            Auto-rebase runs (24h)
          </h2>
          <ul className="space-y-1.5 text-sm text-zinc-400">
            {data.rebaseRuns.length === 0 ? (
              <li className="text-zinc-600">No runs in the last 24 hours.</li>
            ) : (
              data.rebaseRuns.map((r) => (
                <li key={r.id}>
                  <a
                    href={r.html_url}
                    className="text-sky-400 hover:underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {r.conclusion ?? "in progress"} · {r.name}
                  </a>
                  <span className="ml-2 text-xs text-zinc-600">
                    {new Date(r.created_at).toLocaleString()}
                  </span>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          <AlertTriangle className="h-4 w-4 text-amber-500/80" />
          Stuck / escalated (label{" "}
          <code className="rounded bg-zinc-800 px-1">pr-pipeline-escalated</code>)
        </h2>
        <ul className="space-y-2 text-sm text-zinc-400">
          {data.stuck.length === 0 ? (
            <li className="text-zinc-600">None with that label, or not configured.</li>
          ) : (
            data.stuck.map((i) => (
              <li key={i.number}>
                <a
                  href={i.html_url}
                  className="font-mono text-sky-400 hover:underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  #{i.number}
                </a>{" "}
                {i.title}{" "}
                <span className="text-zinc-600">— @{i.author}</span>
                {i.labels.length ? (
                  <span className="ml-2 text-xs text-zinc-500">
                    {i.labels.join(", ")}
                  </span>
                ) : null}
              </li>
            ))
          )}
        </ul>
        <p className="text-xs text-zinc-600">
          Docs:{" "}
          <Link
            href="https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/PR_PIPELINE_AUTOMATION.md"
            className="text-sky-500 hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            PR_PIPELINE_AUTOMATION.md
          </Link>
        </p>
      </section>
    </div>
  );
}
