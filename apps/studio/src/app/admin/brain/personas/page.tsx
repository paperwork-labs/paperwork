import { Suspense } from "react";
import { Bot } from "lucide-react";

import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";

export const dynamic = "force-dynamic";

function TabSkeleton() {
  return (
    <div className="flex flex-col gap-3 py-4" aria-busy="true">
      <div className="h-8 w-full max-w-md animate-pulse rounded-md bg-zinc-800" />
      <div className="h-48 w-full animate-pulse rounded-lg bg-zinc-800" />
    </div>
  );
}

function ComingSoonShell({ tab, owner }: { tab: string; owner: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 py-16 text-center">
      <Bot className="mb-4 h-10 w-10 text-zinc-600" />
      <h2 className="text-base font-semibold text-zinc-300 capitalize">{tab}</h2>
      <p className="mt-2 max-w-sm text-sm text-zinc-500">
        This tab&apos;s content is managed by{" "}
        <strong className="text-zinc-400">{owner}</strong>. The shell is ready and routing
        is wired — content populates when that PR merges.
      </p>
      <span className="mt-4 rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-400">
        {owner} populates
      </span>
    </div>
  );
}

const TABS = [
  { id: "registry" as const, label: "Registry" },
  { id: "cost" as const, label: "Cost" },
  { id: "routing" as const, label: "Routing" },
  { id: "activity" as const, label: "Activity" },
  { id: "model-registry" as const, label: "Model Registry" },
] as const;

export default function BrainPersonasPage() {
  const tabs = TABS.map((t) => ({
    id: t.id,
    label: t.label,
    content: (
      <Suspense fallback={<TabSkeleton />}>
        <ComingSoonShell tab={t.label} owner="PR F" />
      </Suspense>
    ),
  }));

  return (
    <div className="space-y-4">
      <header>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Brain — Personas
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Persona registry, cost attribution, routing rules, activity feed, and model assignments.
          PR F populates all tabs.
        </p>
      </header>
      <TabbedPageShell tabs={tabs} defaultTab="registry" />
    </div>
  );
}
