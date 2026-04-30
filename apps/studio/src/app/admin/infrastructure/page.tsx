import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import InfraOverviewTab from "./tabs/overview-tab";
import ServicesTab from "./tabs/services-tab";
import SecretsTab from "./tabs/secrets-tab";
import LogsTab from "./tabs/logs-tab";
import CostTab from "./tabs/cost-tab";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function InfrastructurePage() {
  const tabs = [
    {
      id: "overview" as const,
      label: "Overview",
      content: <InfraOverviewTab />,
    },
    {
      id: "services" as const,
      label: "Services",
      content: <ServicesTab />,
    },
    {
      id: "secrets" as const,
      label: "Secrets",
      content: <SecretsTab />,
    },
    {
      id: "logs" as const,
      label: "Logs",
      content: <LogsTab />,
    },
    {
      id: "cost" as const,
      label: "Cost",
      content: <CostTab />,
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
