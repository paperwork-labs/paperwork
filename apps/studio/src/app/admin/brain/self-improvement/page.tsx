import { Suspense } from "react";
import { TabbedPageShellNodeNext } from "@/components/layout/TabbedPageShellNext";
import { Sparkles } from "lucide-react";

export const dynamic = "force-dynamic";

function TabSkeleton() {
  return (
    <div className="flex flex-col gap-3 py-4" aria-busy="true">
      <div className="h-8 w-full max-w-md animate-pulse rounded-md bg-zinc-800" />
      <div className="h-48 w-full animate-pulse rounded-lg bg-zinc-800" />
    </div>
  );
}

const TAB_OWNERS: Record<string, string> = {
  learning: "PR M",
  promotions: "PR G",
  outcomes: "PR G",
  retros: "PR P",
  "automation-state": "PR M",
  "procedural-memory": "PR F",
  audits: "PR P",
  index: "PR G",
};

function ComingSoonShell({ label, owner }: { label: string; owner: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 py-16 text-center">
      <Sparkles className="mb-4 h-10 w-10 text-zinc-600" />
      <h2 className="text-base font-semibold text-zinc-300">{label}</h2>
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
  { id: "learning" as const, label: "Learning" },
  { id: "promotions" as const, label: "Promotions" },
  { id: "outcomes" as const, label: "Outcomes" },
  { id: "retros" as const, label: "Retros" },
  { id: "automation-state" as const, label: "Automation State" },
  { id: "procedural-memory" as const, label: "Procedural Memory" },
  { id: "audits" as const, label: "Audits" },
  { id: "index" as const, label: "Index" },
] as const;

export default function BrainSelfImprovementPage() {
  const tabs = TABS.map((t) => ({
    id: t.id,
    label: t.label,
    content: (
      <Suspense fallback={<TabSkeleton />}>
        <ComingSoonShell label={t.label} owner={TAB_OWNERS[t.id] ?? "PR F/G/M/P"} />
      </Suspense>
    ),
  }));

  return (
    <div className="space-y-4">
      <header>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Brain — Self-Improvement
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Learning loop, promotion track, outcome measurement, retrospectives, automation state,
          procedural memory, and audit trail. PRs E/F/G/M/P populate individual tabs.
        </p>
      </header>
      <TabbedPageShellNodeNext tabs={tabs} defaultTab="learning" />
    </div>
  );
}
