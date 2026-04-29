"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { ExternalLink } from "lucide-react";

import { usePersonasInitial } from "../personas-client";
import type { PersonaRow } from "../personas-types";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@paperwork-labs/ui";

const GH_FILE_BASE = "https://github.com/paperwork-labs/paperwork/blob/main";

function fileHref(rel: string) {
  return `${GH_FILE_BASE}/${rel.replace(/^\//, "")}`;
}

export function PersonasTab() {
  const { personas, brainConfigured } = usePersonasInitial();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<PersonaRow | null>(null);

  const rows = useMemo(() => personas ?? [], [personas]);

  return (
    <div className="space-y-4">
      {!brainConfigured && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100/90">
          Brain API is not configured — persona list may be empty. Set{" "}
          <code className="rounded bg-zinc-800 px-1">BRAIN_API_URL</code> and{" "}
          <code className="rounded bg-zinc-800 px-1">BRAIN_API_SECRET</code>.
        </p>
      )}
      {brainConfigured && personas === null && (
        <p className="text-sm text-zinc-400" data-testid="personas-load-error">
          Could not load persona rules from Brain.
        </p>
      )}
      {brainConfigured && personas && personas.length === 0 && (
        <p className="text-sm text-zinc-400">No `.cursor/rules/*.mdc` files were returned.</p>
      )}
      <div className="overflow-x-auto rounded-lg border border-zinc-800">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-zinc-800 bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-2">Persona</th>
              <th className="px-3 py-2">Description</th>
              <th className="px-3 py-2">Model</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id} className="border-b border-zinc-800/80 last:border-0 hover:bg-zinc-900/40">
                <td className="px-3 py-2 font-medium text-zinc-100">
                  <button
                    type="button"
                    className="text-left underline-offset-2 hover:underline"
                    onClick={() => {
                      setSelected(p);
                      setOpen(true);
                    }}
                  >
                    {p.name}
                  </button>
                </td>
                <td className="max-w-md px-3 py-2 text-zinc-400">{p.description || "—"}</td>
                <td className="px-3 py-2 font-mono text-xs text-zinc-300">{p.model ?? "—"}</td>
                <td className="px-3 py-2">
                  <span
                    className={
                      p.status === "active"
                        ? "rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-200"
                        : "rounded-full bg-zinc-600/40 px-2 py-0.5 text-xs text-zinc-300"
                    }
                  >
                    {p.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto border-zinc-800 bg-zinc-950 text-zinc-100">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selected?.name}
              {selected?.relative_path ? (
                <a
                  href={fileHref(selected.relative_path)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-normal text-sky-400 hover:underline"
                >
                  View on GitHub <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                </a>
              ) : null}
            </DialogTitle>
          </DialogHeader>
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
              {selected?.markdown_body?.trim() || "_No body in this rule file._"}
            </ReactMarkdown>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
