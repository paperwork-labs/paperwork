import { redirect } from "next/navigation";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import ServicesTab from "./tabs/services-tab";
import VendorsTab from "./tabs/vendors-tab";
import SecretsTab from "./tabs/secrets-tab";
import CostTab from "./tabs/cost-tab";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type PageProps = { searchParams: Promise<{ tab?: string }> };

export default async function InfrastructurePage({ searchParams }: PageProps) {
  const { tab } = await searchParams;
  if (tab === "overview") {
    redirect("/admin/infrastructure?tab=services");
  }
  if (tab === "logs") {
    redirect("/admin/infrastructure?tab=services&infraView=logs");
  }

  const tabs = [
    {
      id: "services" as const,
      label: "Services",
      content: <ServicesTab />,
    },
    {
      id: "vendors" as const,
      label: "Vendors",
      content: <VendorsTab />,
    },
    {
      id: "secrets" as const,
      label: "Secrets",
      content: <SecretsTab />,
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
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Infrastructure</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Health, deploys, and cost across Vercel + Render + vendor quotas.
        </p>
      </header>
      <TabbedPageShell tabs={tabs} defaultTab="services" />
    </div>
  );
}
