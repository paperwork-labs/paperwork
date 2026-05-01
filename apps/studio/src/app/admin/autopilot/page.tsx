import { CheckCircle2, XCircle, Clock, Zap, AlertTriangle, Bot } from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

import { AutopilotActions } from "./autopilot-actions-client";

export const dynamic = "force-dynamic";

export const metadata = { title: "Autopilot — Studio" };

type DispatchItem = {
  id: string;
  description: string;
  persona: string;
  model: string;
  status: "pending" | "running" | "completed" | "failed" | "vetoed";
  created_at: string;
};

type DispatchLog = {
  items: DispatchItem[];
  summary: {
    total_dispatched: number;
    completed: number;
    failed: number;
    pending: number;
    operating_score: number;
  };
};

async function fetchDispatchLog(): Promise<DispatchLog | null> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return null;

  try {
    const res = await fetch(`${auth.root}/v1/memory/dispatch-log`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = await res.json();
    if (!json.success) return null;
    return json.data as DispatchLog;
  } catch {
    return null;
  }
}

function statusConfig(status: DispatchItem["status"]) {
  switch (status) {
    case "completed":
      return { icon: CheckCircle2, label: "Completed", className: "text-emerald-400 bg-emerald-400/10" };
    case "running":
      return { icon: Zap, label: "Running", className: "text-blue-400 bg-blue-400/10" };
    case "failed":
      return { icon: AlertTriangle, label: "Failed", className: "text-red-400 bg-red-400/10" };
    case "vetoed":
      return { icon: XCircle, label: "Vetoed", className: "text-orange-400 bg-orange-400/10" };
    default:
      return { icon: Clock, label: "Pending", className: "text-zinc-400 bg-zinc-400/10" };
  }
}

export default async function AutopilotPage() {
  const data = await fetchDispatchLog();

  return (
    <div className="space-y-8" data-testid="admin-autopilot-page">
      <HqPageHeader
        title="Autopilot"
        subtitle="Brain's dispatched work — approve or veto with one click"
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Autopilot" },
        ]}
      />

      {/* Daily Briefing Summary */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Daily Briefing
        </h2>
        {data ? (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <BriefingStat label="Dispatched" value={data.summary.total_dispatched} />
            <BriefingStat label="Completed" value={data.summary.completed} className="text-emerald-400" />
            <BriefingStat label="Failed" value={data.summary.failed} className="text-red-400" />
            <BriefingStat label="Pending" value={data.summary.pending} className="text-zinc-300" />
            <div className="flex flex-col items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/80 p-3">
              <span className="text-[10px] uppercase tracking-wide text-zinc-500">Score</span>
              <span className="text-2xl font-bold text-zinc-100">{data.summary.operating_score}</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <AlertTriangle className="h-4 w-4" />
            <span>Unable to reach Brain API — configure BRAIN_API_URL and BRAIN_API_SECRET</span>
          </div>
        )}
      </section>

      {/* Dispatch Cards */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Today&apos;s Dispatches
        </h2>
        {!data || data.items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
            No dispatched tasks today
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.items.map((item) => {
              const cfg = statusConfig(item.status);
              const Icon = cfg.icon;
              return (
                <div
                  key={item.id}
                  className="flex flex-col gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-zinc-100">{item.description}</p>
                    <span
                      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${cfg.className}`}
                    >
                      <Icon className="h-3 w-3" />
                      {cfg.label}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                    <span className="inline-flex items-center gap-1">
                      <Bot className="h-3 w-3" />
                      {item.persona}
                    </span>
                    <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px]">
                      {item.model}
                    </span>
                    <span className="ml-auto text-zinc-600">
                      {new Date(item.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  {item.status === "pending" && <AutopilotActions taskId={item.id} />}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function BriefingStat({
  label,
  value,
  className,
}: {
  label: string;
  value: number;
  className?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/80 p-3">
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
      <span className={`text-2xl font-bold ${className ?? "text-zinc-100"}`}>{value}</span>
    </div>
  );
}
