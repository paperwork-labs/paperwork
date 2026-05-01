"use client";

import { useState, useTransition } from "react";
import { Check, X } from "lucide-react";

import { approveDispatch, vetoDispatch } from "./actions";

export type AutopilotDispatchStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "vetoed";

/** Renders approve/veto controls only when the dispatch is still pending founder review. */
export function AutopilotActionsIfPending({
  status,
  taskId,
  label,
}: {
  status: AutopilotDispatchStatus;
  taskId: string;
  label?: string;
}) {
  if (status !== "pending") return null;
  return <AutopilotActions taskId={taskId} label={label} />;
}

export function AutopilotActions({
  taskId,
  label,
}: {
  taskId: string;
  label?: string;
}) {
  const [isPending, startTransition] = useTransition();
  const [vetoMode, setVetoMode] = useState(false);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<{ ok: boolean; error?: string } | null>(null);

  if (result?.ok) {
    return (
      <span className="text-xs text-emerald-400">Action recorded</span>
    );
  }

  return (
    <div className="space-y-2" data-testid={`autopilot-actions-${taskId}`}>
      {label ? (
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
          {label}
        </p>
      ) : null}
      {!vetoMode ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={isPending}
            onClick={() => {
              startTransition(async () => {
                const r = await approveDispatch(taskId);
                setResult(r);
              });
            }}
            className="inline-flex items-center gap-1 rounded-md border border-emerald-700 bg-emerald-900/40 px-3 py-1.5 text-xs font-medium text-emerald-300 transition hover:bg-emerald-900/70 disabled:opacity-50"
          >
            <Check className="h-3 w-3" />
            Approve
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={() => setVetoMode(true)}
            className="inline-flex items-center gap-1 rounded-md border border-red-800 bg-red-900/30 px-3 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-900/60 disabled:opacity-50"
          >
            <X className="h-3 w-3" />
            Veto
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <input
            type="text"
            placeholder="Reason for veto..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-600 focus:outline-none"
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={isPending || !reason.trim()}
              onClick={() => {
                startTransition(async () => {
                  const r = await vetoDispatch(taskId, reason.trim());
                  setResult(r);
                });
              }}
              className="inline-flex items-center gap-1 rounded-md border border-red-800 bg-red-900/30 px-3 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-900/60 disabled:opacity-50"
            >
              Confirm Veto
            </button>
            <button
              type="button"
              disabled={isPending}
              onClick={() => {
                setVetoMode(false);
                setReason("");
              }}
              className="rounded-md px-3 py-1.5 text-xs text-zinc-400 transition hover:text-zinc-200"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {result && !result.ok && (
        <p className="text-xs text-red-400">{result.error}</p>
      )}
    </div>
  );
}
