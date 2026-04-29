"use client";

import { useMemo, useState } from "react";

import type { MarkdownTable } from "@/lib/personas-types";

import { usePersonasPagePayload } from "../personas-tabs-client";

type SortDir = "asc" | "desc";

function sortRows(
  table: MarkdownTable,
  colIndex: number,
  dir: SortDir,
): string[][] {
  const rows = [...table.rows];
  rows.sort((a, b) => {
    const va = a[colIndex] ?? "";
    const vb = b[colIndex] ?? "";
    const cmp = va.localeCompare(vb, undefined, { numeric: true, sensitivity: "base" });
    return dir === "asc" ? cmp : -cmp;
  });
  return rows;
}

function SortableTable(props: { table: MarkdownTable }) {
  const { table } = props;
  const [sortCol, setSortCol] = useState(0);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(
    () => sortRows(table, sortCol, sortDir),
    [table, sortCol, sortDir],
  );

  function toggleSort(idx: number) {
    if (idx === sortCol) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(idx);
      setSortDir("asc");
    }
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        <thead className="border-b border-border bg-muted/40">
          <tr>
            {table.headers.map((h, idx) => (
              <th key={`${h}-${idx}`} className="px-3 py-2 font-medium">
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-left hover:text-foreground"
                  onClick={() => toggleSort(idx)}
                >
                  {h}
                  {sortCol === idx ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((cells, ri) => (
            <tr key={ri} className="border-b border-border/80 odd:bg-muted/20">
              {cells.map((c, ci) => (
                <td key={ci} className="max-w-[420px] px-3 py-2 align-top text-muted-foreground">
                  <span className="whitespace-pre-wrap break-words">{c}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ModelRegistryTab() {
  const { modelRegistry } = usePersonasPagePayload();

  if (!modelRegistry.source.ok) {
    return (
      <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100" role="alert">
        <p className="font-medium">Model registry file missing or unreadable</p>
        <p className="mt-2">
          Add <code className="rounded bg-zinc-900/80 px-1">docs/AI_MODEL_REGISTRY.md</code> to
          populate this tab.
        </p>
        {"message" in modelRegistry.source ? (
          <p className="mt-2 text-amber-100/90">{modelRegistry.source.message}</p>
        ) : null}
        <p className="mt-2 font-mono text-xs text-amber-100/80">{modelRegistry.source.path}</p>
      </div>
    );
  }

  if (modelRegistry.tables.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Parsed{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">docs/AI_MODEL_REGISTRY.md</code> but
        found no markdown pipe tables in the body (after frontmatter).
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <p className="text-sm text-muted-foreground">
        Tables extracted from{" "}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">docs/AI_MODEL_REGISTRY.md</code>.
        Header clicks sort within each table.
      </p>
      {modelRegistry.tables.map((tbl, i) => (
        <section key={`${tbl.title}-${i}`} className="space-y-2">
          <h2 className="text-base font-semibold text-foreground">{tbl.title}</h2>
          <SortableTable table={tbl} />
        </section>
      ))}
    </div>
  );
}
