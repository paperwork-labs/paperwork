"use client";

import {
  createContext,
  lazy,
  useCallback,
  useContext,
  useMemo,
  type LazyExoticComponent,
  type ComponentType,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  Page,
  PageContainer,
  PageHeader,
  TabbedPageShell,
} from "@paperwork-labs/ui";

import type { PersonasPagePayload } from "@/lib/personas-types";
import { resolvePersonasTab, type PersonasTabId } from "@/lib/personas-tab-params";

const RegistryTab = lazy(() => import("./_tabs/registry-tab"));
const CostTab = lazy(() => import("./_tabs/cost-tab"));
const RoutingTab = lazy(() => import("./_tabs/routing-tab"));
const ActivityTab = lazy(() => import("./_tabs/activity-tab"));
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
    { id: "registry", label: "Registry", Content: RegistryTab },
    { id: "cost", label: "Cost", Content: CostTab },
    { id: "routing", label: "Routing", Content: RoutingTab },
    { id: "activity", label: "Activity", Content: ActivityTab },
    { id: "model-registry", label: "Model registry", Content: ModelRegistryTab },
  ];
}

export function PersonasTabsClient({ data }: { data: PersonasPagePayload }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = resolvePersonasTab(searchParams.get("tab") ?? undefined);

  const onTabChange = useCallback(
    (tab: PersonasTabId) => {
      const q = new URLSearchParams(searchParams.toString());
      q.set("tab", tab);
      router.replace(`/admin/brain/personas?${q.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const tabs = useMemo(() => shellTabs(), []);

  return (
    <PersonasDataContext.Provider value={data}>
      <Page fullWidth>
        <PageContainer width="wide">
          <PageHeader
            title="Personas"
            subtitle="Cursor rule roster, Brain dispatch costs, EA routing map, activity, and AI model registry."
          />
          <TabbedPageShell<PersonasTabId>
            tabs={tabs}
            defaultTab="registry"
            activeTab={activeTab}
            onTabChange={onTabChange}
          />
        </PageContainer>
      </Page>
    </PersonasDataContext.Provider>
  );
}
