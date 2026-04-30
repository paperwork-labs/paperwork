"use client";

import {
  createContext,
  lazy,
  useContext,
  useMemo,
  type ComponentType,
  type LazyExoticComponent,
} from "react";

import { CheckCircle2, CircleDollarSign, Radio, Users } from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import { TabbedPageShell } from "@/components/layout/TabbedPageShellNext";
import type { PersonasTabId } from "@/lib/personas-tab-params";
import type { PersonasPagePayload } from "@/lib/personas-types";

const RegistryTab = lazy(() => import("./_tabs/registry-tab"));
const ActivityTab = lazy(() => import("./_tabs/activity-tab"));
const PromotionsQueueTab = lazy(() => import("./_tabs/promotions-queue-tab"));
const OpenRolesTab = lazy(() => import("./_tabs/open-roles-tab"));
const CostTab = lazy(() => import("./_tabs/cost-tab"));
const RoutingTab = lazy(() => import("./_tabs/routing-tab"));
const ModelRegistryTab = lazy(() => import("./_tabs/model-registry-tab"));

const PersonasDataContext = createContext<PersonasPagePayload | null>(null);

export function usePersonasPagePayload(): PersonasPagePayload {
  const v = useContext(PersonasDataContext);
  if (!v) {
    throw new Error("usePersonasPagePayload must be used within PersonasTabsClient");
  }
  return v;
}

function shellTabs(): readonly {
  id: PersonasTabId;
  label: string;
  Content: LazyExoticComponent<ComponentType>;
}[] {
  return [
    { id: "registry", label: "Specs", Content: RegistryTab },
    { id: "activity", label: "Activity stream", Content: ActivityTab },
    { id: "promotions-queue", label: "Promotions queue", Content: PromotionsQueueTab },
    { id: "open-roles", label: "Open roles", Content: OpenRolesTab },
    { id: "cost", label: "Cost", Content: CostTab },
    { id: "routing", label: "Routing", Content: RoutingTab },
    { id: "model-registry", label: "Model registry", Content: ModelRegistryTab },
  ];
}

export function PersonasTabsClient({ data }: { data: PersonasPagePayload }) {
  const tabs = useMemo(() => shellTabs(), []);

  return (
    <PersonasDataContext.Provider value={data}>
      <div className="space-y-8">
        {data.brainApiError && (
          <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-300">
            <span className="font-semibold">Brain API error — showing snapshot data:</span>{" "}
            {data.brainApiError}
          </div>
        )}

        <HqPageHeader
          title="People"
          subtitle="AI team members — Cursor rule specs, dispatch activity, promotions, spend, routing, and registry."
          breadcrumbs={[
            { label: "Admin", href: "/admin" },
            { label: "Brain", href: "/admin/brain/self-improvement" },
            { label: "People" },
          ]}
        />

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <HqStatCard
            label="Active personas"
            value={data.dashboard.activePersonas}
            icon={<Users className="h-3.5 w-3.5 text-zinc-500" />}
            helpText="Rules in .cursor/rules"
          />
          <HqStatCard
            label="Dispatches today"
            value={data.dashboard.dispatchesToday}
            icon={<Radio className="h-3.5 w-3.5 text-zinc-500" />}
            helpText="agent_dispatch_log.json (UTC day)"
          />
          <HqStatCard
            label="Approval rate"
            value={data.dashboard.approvalRateLabel}
            icon={<CheckCircle2 className="h-3.5 w-3.5 text-zinc-500" />}
            helpText="Merged vs failed outcomes (last 30d)"
          />
          <HqStatCard
            label="Daily cost"
            value={data.dashboard.dailyCostStatLabel}
            icon={<CircleDollarSign className="h-3.5 w-3.5 text-zinc-500" />}
            helpText="$ / persona / day — PR-10"
          />
        </div>

        <TabbedPageShell<PersonasTabId> tabs={tabs} defaultTab="registry" />
      </div>
    </PersonasDataContext.Provider>
  );
}
