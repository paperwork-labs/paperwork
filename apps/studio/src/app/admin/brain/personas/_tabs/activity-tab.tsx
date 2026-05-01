"use client";

import type { ActivityActionType } from "@/lib/personas-types";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

import { usePersonasPagePayload } from "../personas-tabs-client";

const ACCENT_DOT_CLASSES = [
  "bg-emerald-400 ring-emerald-400/50",
  "bg-sky-400 ring-sky-400/50",
  "bg-violet-400 ring-violet-400/50",
  "bg-amber-400 ring-amber-400/50",
  "bg-rose-400 ring-rose-400/50",
  "bg-cyan-400 ring-cyan-400/50",
  "bg-fuchsia-400 ring-fuchsia-400/50",
  "bg-lime-400 ring-lime-400/50",
];

function personaAccentDotClass(personaKey: string): string {
  let h = 0;
  for (let i = 0; i < personaKey.length; i++) {
    h = Math.imul(31, h) + personaKey.charCodeAt(i);
  }
  const idx = Math.abs(h) % ACCENT_DOT_CLASSES.length;
  return ACCENT_DOT_CLASSES[idx]!;
}

function formatTimestamp(iso: string): string {
  if (iso === "—") return iso;
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return iso;
  return new Date(ms).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function actionLabel(action: ActivityActionType | undefined): string {
  switch (action ?? "dispatch") {
    case "review":
      return "Review";
    case "escalate":
      return "Escalate";
    case "unknown":
      return "Event";
    default:
      return "Dispatch";
  }
}

function actionBadgeClasses(action: ActivityActionType | undefined): string {
  switch (action ?? "dispatch") {
    case "review":
      return "border-sky-500/35 bg-sky-500/15 text-sky-200";
    case "escalate":
      return "border-amber-500/35 bg-amber-500/15 text-amber-200";
    case "unknown":
      return "border-zinc-600 bg-zinc-800/80 text-zinc-300";
    default:
      return "border-emerald-500/35 bg-emerald-500/15 text-emerald-200";
  }
}

export default function ActivityTab() {
  const { activity } = usePersonasPagePayload();
  const liveFromBrain =
    activity.source.ok && activity.source.path.includes("agent-dispatch-log");

  return (
    <div className="space-y-4">
      {!activity.source.ok ? (
        <div
          className="rounded-lg border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-100"
          role="alert"
        >
          <p className="font-medium">Persona dispatch activity unavailable</p>
          <p className="mt-1">
            {"message" in activity.source ? activity.source.message : "Read failed"}{" "}
            <code className="rounded bg-zinc-900/80 px-1">{activity.source.path}</code>
          </p>
        </div>
      ) : liveFromBrain ? (
        <p className="text-sm text-zinc-400">
          Live persona actions from Brain API{" "}
          <code className="rounded bg-zinc-900 px-1 py-0.5 text-xs text-zinc-300">
            agent_dispatch_log.json
          </code>{" "}
          (newest first).
        </p>
      ) : (
        <p className="text-sm text-zinc-400">
          Recent persona-backed dispatches (newest first) from{" "}
          <code className="rounded bg-zinc-900 px-1 py-0.5 text-xs text-zinc-300">
            apis/brain/data/agent_dispatch_log.json
          </code>{" "}
          in this checkout.
        </p>
      )}

      {activity.note && activity.rows.length > 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-zinc-400">
          {activity.note}
        </div>
      ) : null}

      {activity.source.ok && activity.rows.length === 0 ? (
        <HqEmptyState
          title="No dispatch activity yet"
          description={
            activity.note ??
            "Persona-backed dispatches will appear here once Brain records events in agent_dispatch_log.json."
          }
        />
      ) : null}

      {activity.rows.length > 0 ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">
          <ul className="space-y-0">
            {activity.rows.map((row, i) => {
              const display = row.personaDisplayName ?? row.persona;
              const initial = display.trim().charAt(0).toUpperCase() || "?";
              const dotClass = personaAccentDotClass(row.persona);
              const action = row.actionType ?? "dispatch";
              const isLast = i === activity.rows.length - 1;

              return (
                <li key={`${row.dispatchedAt}-${i}`} className="relative flex gap-4">
                  <div className="flex w-11 shrink-0 flex-col items-center">
                    {i > 0 ? (
                      <div className="h-3 w-px shrink-0 bg-zinc-800" aria-hidden />
                    ) : (
                      <div className="h-3 shrink-0" aria-hidden />
                    )}
                    <div
                      className={`relative z-[1] shrink-0 rounded-full ring-4 ring-zinc-950 ${dotClass}`}
                      style={{ width: "12px", height: "12px" }}
                      aria-hidden
                    />
                    {!isLast ? (
                      <div className="mt-0 min-h-[4.5rem] w-px flex-1 bg-zinc-800" aria-hidden />
                    ) : (
                      <div className="h-3 shrink-0" aria-hidden />
                    )}
                  </div>

                  <article className={`min-w-0 flex-1 ${isLast ? "" : "pb-8"}`}>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                      <div className="flex flex-wrap items-start gap-3">
                        <div
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-zinc-700 bg-zinc-900 text-xs font-semibold text-zinc-200"
                          aria-hidden
                        >
                          {initial}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2 gap-y-1">
                            <time
                              className="font-mono text-xs tabular-nums text-zinc-500"
                              dateTime={row.dispatchedAt !== "—" ? row.dispatchedAt : undefined}
                            >
                              {formatTimestamp(row.dispatchedAt)}
                            </time>
                            <span
                              className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${actionBadgeClasses(action)}`}
                            >
                              {actionLabel(action)}
                            </span>
                            <span className="text-sm font-medium text-zinc-100">{display}</span>
                          </div>

                          <p className="mt-2 text-sm leading-snug text-zinc-300">
                            <span className="text-zinc-500">Target:</span>{" "}
                            <span className="font-medium text-zinc-200">
                              {row.targetLabel ?? row.workstreamTag}
                            </span>
                            <span className="mx-2 text-zinc-600">·</span>
                            <span className="text-zinc-500">Outcome:</span>{" "}
                            <span className="text-zinc-300">{row.successLabel}</span>
                            {row.costLabel !== "—" ? (
                              <>
                                <span className="mx-2 text-zinc-600">·</span>
                                <span className="text-zinc-500">Est.:</span>{" "}
                                <span className="text-zinc-400">{row.costLabel}</span>
                              </>
                            ) : null}
                          </p>

                          {row.description ? (
                            <p className="mt-2 border-t border-zinc-800/80 pt-2 text-xs leading-relaxed text-zinc-400">
                              {row.description}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </article>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
