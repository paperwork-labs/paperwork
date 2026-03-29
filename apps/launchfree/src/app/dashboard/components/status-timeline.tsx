"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";
import type {
  FormationDashboardStatus,
  FormationStatusEvent,
} from "@/lib/dashboard-formations";

export type { FormationStatusEvent };

const currentStepClass: Record<FormationDashboardStatus, string> = {
  draft: "border-slate-400 bg-slate-800 text-slate-100",
  pending: "border-amber-400 bg-amber-500/20 text-amber-100",
  submitted: "border-sky-400 bg-sky-500/20 text-sky-100",
  confirmed: "border-emerald-400 bg-emerald-500/20 text-emerald-100",
  failed: "border-red-400 bg-red-500/20 text-red-100",
};

function formatTimestamp(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function statusTitle(status: FormationDashboardStatus): string {
  const labels: Record<FormationDashboardStatus, string> = {
    draft: "Draft",
    pending: "Pending",
    submitted: "Submitted",
    confirmed: "Confirmed",
    failed: "Failed",
  };
  return labels[status];
}

export interface StatusTimelineProps {
  events: FormationStatusEvent[];
}

export function StatusTimeline({ events }: StatusTimelineProps) {
  const ordered = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  const lastIndex = ordered.length - 1;

  return (
    <ol className="relative space-y-0 pl-2">
      {ordered.map((event, i) => {
        const isCurrent = i === lastIndex;
        const isComplete = i < lastIndex;

        return (
          <motion.li
            key={`${event.status}-${event.timestamp}-${i}`}
            className="relative pb-8 last:pb-0"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
          >
            {i < lastIndex ? (
              <span
                className="absolute left-[15px] top-8 h-[calc(100%-0.5rem)] w-px bg-gradient-to-b from-teal-500/50 to-slate-700/80"
                aria-hidden
              />
            ) : null}
            <div className="flex gap-4">
              <div className="relative z-10 flex shrink-0 flex-col items-center">
                <motion.span
                  className={`flex size-8 items-center justify-center rounded-full border-2 text-xs font-semibold ${
                    isCurrent
                      ? `${currentStepClass[event.status]} shadow-[0_0_20px_rgba(45,212,191,0.2)]`
                      : "border-slate-600 bg-slate-800/90 text-slate-500"
                  }`}
                  animate={isCurrent ? { scale: [1, 1.03, 1] } : { scale: 1 }}
                  transition={{
                    duration: 2.5,
                    repeat: isCurrent ? Infinity : 0,
                    ease: "easeInOut",
                  }}
                >
                  {isComplete ? (
                    <Check className="size-4 text-teal-400" strokeWidth={2.5} />
                  ) : (
                    <span className="uppercase">{event.status[0]}</span>
                  )}
                </motion.span>
              </div>
              <div className="min-w-0 flex-1 pt-0.5">
                <p
                  className={`text-sm font-medium ${
                    isCurrent ? "text-teal-300" : "text-slate-300"
                  }`}
                >
                  {statusTitle(event.status)}
                  {isCurrent ? (
                    <span className="ml-2 text-xs font-normal text-teal-500/90">
                      (current)
                    </span>
                  ) : null}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {formatTimestamp(event.timestamp)}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">
                  {event.description}
                </p>
              </div>
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}
