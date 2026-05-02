"use client";

import Link from "next/link";
import type { ReactNode } from "react";

const toggleActive =
  "inline-flex rounded-md px-3 py-1.5 text-xs font-medium text-zinc-100 bg-zinc-800/90 ring-1 ring-zinc-700/80";
const toggleInactive =
  "inline-flex rounded-md px-3 py-1.5 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50";

export function PeopleAdminShell({
  view,
  directory,
  workspace,
}: {
  view: string | undefined;
  directory: ReactNode;
  workspace: ReactNode;
}) {
  const isWorkspace = view === "workspace";
  return (
    <>
      <div className="mb-6 flex w-fit gap-1 rounded-lg border border-zinc-800 p-1">
        <Link href="/admin/people" className={!isWorkspace ? toggleActive : toggleInactive}>
          Directory
        </Link>
        <Link
          href="/admin/people?view=workspace"
          className={isWorkspace ? toggleActive : toggleInactive}
        >
          Workspace
        </Link>
      </div>
      {isWorkspace ? workspace : directory}
    </>
  );
}
