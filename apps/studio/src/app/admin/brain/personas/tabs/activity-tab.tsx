"use client";

import Link from "next/link";

import { usePersonasInitial } from "../personas-client";

export function ActivityTab() {
  const { activity, brainConfigured } = usePersonasInitial();

  if (!brainConfigured) {
    return (
      <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100/90">
        Brain API is not configured — activity unavailable.
      </p>
    );
  }

  if (!activity) {
    return <p className="text-sm text-zinc-400">Could not load activity.</p>;
  }

  if (activity.parse_error) {
    return <p className="text-sm text-rose-300">persona_activity.json exists but could not be parsed.</p>;
  }

  if (!activity.has_file || activity.events.length === 0) {
    return (
      <p className="text-sm text-zinc-400" data-testid="activity-empty-state">
        No persona activity recorded yet — events appear here once Brain logs invocations to
        `apis/brain/data/persona_activity.json`.
      </p>
    );
  }

  return (
    <ol className="space-y-4 border-l border-zinc-800 pl-4">
      {activity.events.map((e, i) => (
        <li key={e.id ?? `${e.at}-${i}`} className="relative">
          <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-sky-500" aria-hidden />
          <div className="space-y-1 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
            <div className="flex flex-wrap items-baseline gap-2 text-sm">
              <span className="font-semibold text-zinc-100">{e.persona ?? "unknown"}</span>
              <span className="text-xs text-zinc-500">{e.at ?? ""}</span>
            </div>
            {e.conversation_id ? (
              <Link
                href={`/admin/brain/conversations/${e.conversation_id}`}
                className="text-xs text-sky-400 hover:underline"
              >
                Conversation {e.conversation_id}
              </Link>
            ) : null}
            {e.input_excerpt ? (
              <p className="text-xs text-zinc-400">
                <span className="font-medium text-zinc-500">In:</span> {e.input_excerpt}
              </p>
            ) : null}
            {e.output_excerpt ? (
              <p className="text-xs text-zinc-400">
                <span className="font-medium text-zinc-500">Out:</span> {e.output_excerpt}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
