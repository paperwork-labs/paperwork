import { Suspense } from "react";

import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import InfraOverviewTab from "./tabs/overview-tab";
import ServicesTab from "./tabs/services-tab";
import SecretsTab from "./tabs/secrets-tab";
import LogsTab from "./tabs/logs-tab";
import CostTab from "./tabs/cost-tab";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function TabSkeleton() {
  return (
    <div className="flex flex-col gap-3 py-4" aria-busy="true">
      <div className="h-8 w-full max-w-md animate-pulse rounded-md bg-zinc-800" />
      <div className="h-48 w-full animate-pulse rounded-lg bg-zinc-800" />
    </div>
  );
}

export default function InfrastructurePage() {
  const tabs = [
    {
      id: "overview" as const,
      label: "Overview",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <InfraOverviewTab />
        </Suspense>
      ),
    },
    {
      id: "services" as const,
      label: "Services",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <ServicesTab />
        </Suspense>
      ),
    },
    {
      id: "secrets" as const,
      label: "Secrets",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <SecretsTab />
        </Suspense>
      ),
    },
    {
      id: "logs" as const,
      label: "Logs",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <LogsTab />
        </Suspense>
      ),
    },
    {
      id: "cost" as const,
      label: "Cost",
      content: (
        <Suspense fallback={<TabSkeleton />}>
          <CostTab />
        </Suspense>
      ),
    },
  ] as const;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Infrastructure
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Services health, secrets vault, logs, and cost tracking.
        </p>
      </header>
      <TabbedPageShell tabs={tabs} defaultTab="overview" />
    </div>
  );
}
