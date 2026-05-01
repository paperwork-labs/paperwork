import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import OverviewTab from "./tabs/overview-tab";
import AnalyticsTab from "./tabs/analytics-tab";

export const dynamic = "force-dynamic";

export default function ArchitecturePage() {
  const tabs = [
    {
      id: "overview" as const,
      label: "Overview",
      content: <OverviewTab />,
    },
    {
      id: "analytics" as const,
      label: "Analytics",
      content: <AnalyticsTab />,
    },
  ] as const;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Architecture
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Interactive system graph and dependency analytics.
        </p>
      </header>
      <TabbedPageShell tabs={tabs} defaultTab="overview" />
    </div>
  );
}
