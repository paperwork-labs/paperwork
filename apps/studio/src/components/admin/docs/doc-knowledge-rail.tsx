import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Atom,
  BookOpenCheck,
  Link2,
  ListTree,
  Waypoints,
} from "lucide-react";
import type { ReactNode } from "react";

import { getKnowledgeRailForSlug } from "@/lib/knowledge-graph-data";

type Props = {
  slug: string;
  markdownBody: string;
};

function SectionTitle(props: { icon: LucideIcon; children: ReactNode }) {
  const Icon = props.icon;
  return (
    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
      <Icon className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
      {props.children}
    </div>
  );
}

export function DocKnowledgeRail({ slug, markdownBody }: Props) {
  const rail = getKnowledgeRailForSlug(slug, markdownBody);
  const backlinksLabel =
    rail.linkedFrom.count === 1 ? "1 backlink" : `${rail.linkedFrom.count} backlinks`;

  return (
    <aside
      className="space-y-5 rounded-xl border border-zinc-800 bg-zinc-950/55 p-4 text-xs text-zinc-300 lg:sticky lg:top-24"
      aria-label="Doc knowledge graph"
      data-testid="doc-backlinks-panel"
    >
      <div className="space-y-1 border-b border-zinc-800/80 pb-4">
        <SectionTitle icon={Atom}>Knowledge graph</SectionTitle>
        <p className="text-[11px] text-zinc-500">
          {rail.inIndexedGraph
            ? `Indexed node · ~${rail.stats.read_time_min} min read · ${rail.stats.freshness}`
            : "Slug not in bundled graph · backlinks from edges when present"}
        </p>
      </div>

      <div className="space-y-2">
        <SectionTitle icon={Link2}>Linked from</SectionTitle>
        <p className="text-zinc-500" data-testid="doc-linked-from-count">
          {backlinksLabel}
        </p>
        {rail.linkedFrom.topLinkers.length === 0 ? (
          <p className="text-[11px] text-zinc-600">No explicit wiki edges point here yet.</p>
        ) : (
          <ol className="list-decimal space-y-1 pl-4 text-[11px] text-sky-300/90 marker:text-zinc-600">
            {rail.linkedFrom.topLinkers.map((d) => (
              <li key={d.slug}>
                <Link
                  href={`/admin/docs/${d.slug}`}
                  className="hover:text-sky-200 underline-offset-4 hover:underline"
                >
                  {d.title}
                </Link>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="space-y-2">
        <SectionTitle icon={ListTree}>Links to</SectionTitle>
        {rail.linksOut.length === 0 ? (
          <p className="text-[11px] text-zinc-600">
            No forward wiki/doc targets merged from markdown + bundled edges yet.
          </p>
        ) : (
          <ul className="space-y-1 text-[11px]">
            {rail.linksOut.map((d) => (
              <li key={d.slug}>
                <Link
                  href={`/admin/docs/${d.slug}`}
                  className="text-sky-300/90 hover:text-sky-200 underline-offset-4 hover:underline"
                >
                  {d.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2">
        <SectionTitle icon={BookOpenCheck}>Related runbooks</SectionTitle>
        {rail.relatedRunbooks.length === 0 ? (
          <p className="text-[11px] text-zinc-600">None surfaced from facets or markdown.</p>
        ) : (
          <ul className="space-y-1 text-[11px]" data-testid="doc-related-runbooks">
            {rail.relatedRunbooks.map((r) =>
              r.hrefSlug ? (
                <li key={r.hrefSlug}>
                  <Link
                    href={`/admin/docs/${r.hrefSlug}`}
                    className="text-emerald-300/85 hover:text-emerald-200 underline-offset-4 hover:underline"
                  >
                    {r.name}
                  </Link>
                </li>
              ) : (
                <li key={r.name} className="text-zinc-400">
                  {r.name}
                </li>
              ),
            )}
          </ul>
        )}
      </div>

      <div className="space-y-2">
        <SectionTitle icon={Waypoints}>Related workstreams</SectionTitle>
        {rail.relatedWorkstreams.length === 0 ? (
          <p className="text-[11px] text-zinc-600">
            No <code className="text-zinc-500">[[ws:WS-NN]]</code> references in facets or markdown.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-1.5 text-[11px]" data-testid="doc-related-workstreams">
            {rail.relatedWorkstreams.map((ws) => (
              <li
                key={ws}
                className="rounded-md bg-indigo-500/15 px-2 py-1 font-medium text-indigo-200 ring-1 ring-indigo-500/25"
              >
                {ws}
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
