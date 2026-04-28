"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { Workstream } from "@/lib/workstreams/schema";

import {
  formatRelativeActivity,
  ownerBadgeClass,
  statusPillClass,
} from "./display-utils";

export function SortableWorkstreamRow({
  ws,
  rank,
}: {
  ws: Workstream;
  rank: number;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: ws.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const prHref =
    ws.last_pr != null
      ? `https://github.com/paperwork-labs/paperwork/pull/${ws.last_pr}`
      : null;

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={`rounded-lg border border-zinc-800/90 bg-zinc-950/35 ring-1 ring-zinc-800/50 transition-shadow ${
        isDragging ? "z-10 opacity-95 shadow-lg shadow-black/40 ring-zinc-600" : ""
      }`}
    >
      <div className="flex flex-col gap-3 p-3 md:flex-row md:items-start md:gap-4">
        <div className="flex shrink-0 items-center gap-2 md:w-36">
          <button
            type="button"
            className="touch-none rounded-md border border-transparent p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
            aria-label={`Drag to reorder ${ws.title}`}
            {...attributes}
            {...listeners}
          >
            <GripVertical className="h-4 w-4" />
          </button>
          <span className="font-mono text-xs tabular-nums text-zinc-500">
            #{rank}
          </span>
          <span className="rounded-md bg-zinc-800/90 px-2 py-0.5 font-mono text-[11px] font-semibold text-zinc-300 ring-1 ring-zinc-700/80">
            {ws.track}
          </span>
        </div>

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="min-w-0 flex-1 text-sm font-medium text-zinc-100">
              {ws.title}
            </p>
            <span
              className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${statusPillClass(ws.status)}`}
            >
              {ws.status.replace(/_/g, " ")}
            </span>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize ring-1 ${ownerBadgeClass(ws.owner)}`}
            >
              {ws.owner}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-400">
            <span title={ws.last_activity}>
              {formatRelativeActivity(ws.last_activity)}
            </span>
            {prHref ? (
              <Link
                href={prHref}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-sky-400 hover:text-sky-300"
              >
                PR #{ws.last_pr}
              </Link>
            ) : (
              <span className="text-zinc-600">No PR yet</span>
            )}
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-sky-700 to-emerald-600"
                  style={{ width: `${ws.percent_done}%` }}
                />
              </div>
              <span className="w-10 shrink-0 text-right font-mono text-[11px] text-zinc-400">
                {ws.percent_done}%
              </span>
            </div>
          </div>

          {ws.blockers.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {ws.blockers.map((b) => (
                <span
                  key={b}
                  className="max-w-full truncate rounded-md bg-rose-950/40 px-2 py-0.5 text-[11px] text-rose-200 ring-1 ring-rose-800/50"
                  title={b}
                >
                  {b}
                </span>
              ))}
            </div>
          ) : null}

          <NotesCell ws={ws} />
        </div>
      </div>
    </li>
  );
}

function NotesCell({ ws }: { ws: Workstream }) {
  const [open, setOpen] = useState(false);
  const max = 140;
  const needsTrim = ws.notes.length > max;
  const shown =
    open || !needsTrim ? ws.notes : `${ws.notes.slice(0, max).trim()}…`;

  if (!ws.notes) {
    return <span className="text-zinc-600">—</span>;
  }

  return (
    <div className="space-y-1">
      <p className="whitespace-pre-wrap text-xs leading-snug text-zinc-400">
        {shown}
      </p>
      {needsTrim ? (
        <button
          type="button"
          className="text-[11px] font-medium text-sky-400 hover:text-sky-300"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}
