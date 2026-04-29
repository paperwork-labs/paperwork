import { Suspense } from "react";
import { TabbedPageShellNodeNext } from "@/components/layout/TabbedPageShellNext";
import OverviewTab from "./tabs/overview-tab";
import AnalyticsTab from "./tabs/analytics-tab";
import WorkflowsTab from "./tabs/workflows-tab";
import IntegrationsTab from "./tabs/integrations-tab";

export const dynamic = "force-dynamic";

function TabSkeleton() {
  return (
    <div className="flex flex-col gap-3 py-4" aria-busy="true">
      <div className="h-8 w-full max-w-md animate-pulse rounded-md bg-zinc-800" />
      <div className="h-48 w-full animate-pulse rounded-lg bg-zinc-800" />
    </div>
  );
}

export default function ArchitecturePage() {
  const tabs = [
    {
      id: "overview" as const,
      label: "Overview",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <OverviewTab />
        </Suspense>
      ),
    },
    {
      id: "analytics" as const,
      label: "Analytics",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <AnalyticsTab />
        </Suspense>
      ),
    },
    {
      id: "workflows" as const,
      label: "Workflows",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <WorkflowsTab />
        </Suspense>
      ),
    },
    {
      id: "integrations" as const,
      label: "Integrations",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <IntegrationsTab />
        </Suspense>
      ),
    },
  ] as const;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Architecture
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          System graph, analytics, workflows, and integrations.
        </p>
      </header>
      <TabbedPageShellNodeNext tabs={tabs} defaultTab="overview" />
    </div>
  );
}
