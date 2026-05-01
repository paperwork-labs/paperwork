import { useMemo } from "react";

import { DocsHubDocCard } from "./docs-hub-doc-card";
import { buildTeamSections, type PersonaTeamSection } from "./docs-hub-persona";
import type { DocHubEntry } from "@/lib/docs";

export function DocsHubPersonaView({ entries }: { entries: DocHubEntry[] }) {
  const sections = useMemo(() => buildTeamSections(entries), [entries]);

  return (
    <div className="space-y-10" data-testid="docs-hub-persona-view">
      {sections.map((section: PersonaTeamSection) => (
        <section
          key={section.team}
          className="space-y-4"
          aria-labelledby={`persona-team-${section.team.replace(/\s+/g, "-").toLowerCase()}`}
          data-team={section.team}
        >
          <header className="space-y-1">
            <h2
              id={`persona-team-${section.team.replace(/\s+/g, "-").toLowerCase()}`}
              className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400"
            >
              {section.team}
            </h2>
            <p className="max-w-2xl text-sm text-zinc-500">{section.blurb}</p>
          </header>

          <div className="space-y-2 pl-1">
            {section.personas.map(({ slug, docs }: { slug: string; docs: DocHubEntry[] }) => (
              <details
                key={slug}
                className="group rounded-lg border border-zinc-800/80 bg-zinc-950/30"
              >
                <summary className="cursor-pointer select-none list-none px-3 py-2 text-sm font-medium text-zinc-200 marker:content-none [&::-webkit-details-marker]:hidden">
                  <span className="inline-flex items-center gap-2">
                    <span className="text-zinc-500 transition group-open:rotate-90">▸</span>
                    <span>
                      {slug}{" "}
                      <span className="font-normal text-zinc-500">
                        ({docs.length} doc{docs.length === 1 ? "" : "s"})
                      </span>
                    </span>
                  </span>
                </summary>
                <div className="grid gap-3 border-t border-zinc-800/60 p-3 sm:grid-cols-2 lg:grid-cols-3">
                  {docs.map((doc: DocHubEntry) => (
                    <DocsHubDocCard key={`${slug}-${doc.slug}`} doc={doc} />
                  ))}
                </div>
              </details>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
