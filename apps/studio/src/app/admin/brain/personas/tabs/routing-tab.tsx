"use client";

import { ExternalLink } from "lucide-react";

import { Button } from "@paperwork-labs/ui";

import { usePersonasInitial } from "../personas-client";

const GH_FILE_BASE = "https://github.com/paperwork-labs/paperwork/blob/main";

export function RoutingTab() {
  const { routing } = usePersonasInitial();
  const editPath = routing?.edit_path ?? "apis/brain/data/persona_routing.json";
  const href = `${GH_FILE_BASE}/${editPath.replace(/^\//, "")}`;

  if (!routing) {
    return <p className="text-sm text-zinc-400">Could not load routing rules.</p>;
  }

  const tagEntries = Object.entries(routing.tag_to_persona ?? {});
  const kwEntries = Object.entries(routing.content_keyword_to_persona ?? {});

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-400">
          {routing.derived_from_code
            ? "Showing Brain router tables (no persona_routing.json yet)."
            : "Loaded from Brain data file."}
        </p>
        <Button variant="outline" size="sm" asChild className="border-zinc-700 bg-zinc-900 text-zinc-100">
          <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5">
            Edit source <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          </a>
        </Button>
      </div>
      {routing.note ? <p className="text-xs text-zinc-500">{routing.note}</p> : null}
      <section className="space-y-2">
        <h2 className="text-base font-medium text-zinc-100">Tag → persona</h2>
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/60 text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-3 py-2">Tag / channel id</th>
                <th className="px-3 py-2">Persona</th>
              </tr>
            </thead>
            <tbody>
              {tagEntries.map(([tag, persona]) => (
                <tr key={tag} className="border-b border-zinc-800/80 last:border-0">
                  <td className="px-3 py-2 font-mono text-xs text-zinc-300">{tag}</td>
                  <td className="px-3 py-2 text-zinc-200">{persona}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="space-y-2">
        <h2 className="text-base font-medium text-zinc-100">Content keyword → persona</h2>
        <div className="space-y-2">
          {kwEntries.map(([persona, kws]) => (
            <div key={persona} className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2">
              <div className="font-medium text-zinc-100">{persona}</div>
              <p className="text-xs text-zinc-400">{kws.join(", ")}</p>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h2 className="text-base font-medium text-zinc-100">Default fallback</h2>
        <p className="text-sm text-zinc-300">{routing.default_persona ?? "ea"}</p>
      </section>
    </div>
  );
}
