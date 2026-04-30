import type { ReactNode } from "react";
import Link from "next/link";

export type HqEmptyStateAction =
  | { label: string; onClick: () => void }
  | { label: string; href: string };

export type HqEmptyStateProps = {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: HqEmptyStateAction;
};

/** Intentional empty state — not loading, not error, not missing credentials. */
export function HqEmptyState({ icon, title, description, action }: HqEmptyStateProps) {
  return (
    <div
      data-testid="hq-empty-state"
      className="flex flex-col items-center justify-center rounded-xl border border-zinc-800/80 bg-zinc-950/40 px-6 py-10 text-center"
    >
      {icon ? <div className="mb-3 text-zinc-400">{icon}</div> : null}
      <p className="text-sm font-medium text-zinc-200">{title}</p>
      {description ? <p className="mt-2 max-w-md text-sm text-zinc-400">{description}</p> : null}
      {action ? (
        <div className="mt-5">
          {"href" in action ? (
            <Link
              href={action.href}
              className="inline-flex rounded-lg border border-zinc-600 bg-zinc-800/80 px-4 py-2 text-sm font-medium text-zinc-100 motion-safe:transition-colors hover:bg-zinc-800"
            >
              {action.label}
            </Link>
          ) : (
            <button
              type="button"
              onClick={action.onClick}
              className="inline-flex rounded-lg border border-zinc-600 bg-zinc-800/80 px-4 py-2 text-sm font-medium text-zinc-100 motion-safe:transition-colors hover:bg-zinc-800"
            >
              {action.label}
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}
