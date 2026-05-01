"use client";

import Link from "next/link";

import { groupDocsByPersona, TEAM_DESCRIPTIONS, type HubDocForPersona } from "./docs-hub-persona";

export function DocsHubPersonaView({ docs }: { docs: HubDocForPersona[] }) {
  const groups = groupDocsByPersona(docs);

  return (
    <div className="space-y-8">
      {groups.map((group) => (
        <section key={group.team}>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-400">{group.team}</h2>
          <p className="mt-1 text-sm text-zinc-500">{TEAM_DESCRIPTIONS[group.team]}</p>
          <div className="mt-3 space-y-2">
            {group.personas.map((p) => (
              <details key={p.slug} className="rounded-lg border border-zinc-800 bg-zinc-900/40">
                <summary className="cursor-pointer px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/80">
                  <span className="font-medium">{p.slug}</span>
                  <span className="ml-2 text-xs text-zinc-500">
                    {p.docCount} doc{p.docCount === 1 ? "" : "s"}
                  </span>
                </summary>
                <ul className="space-y-2 border-t border-zinc-800 p-3">
                  {p.docs.map((d) => (
                    <li key={`${p.slug}-${d.slug}`}>
                      <Link
                        href={`/admin/docs/${d.slug}`}
                        className="block rounded px-2 py-1.5 hover:bg-zinc-800/50"
                      >
                        <span className="text-sm text-zinc-100">{d.title}</span>
                        {d.summary ? <span className="block text-xs text-zinc-500">{d.summary}</span> : null}
                      </Link>
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
