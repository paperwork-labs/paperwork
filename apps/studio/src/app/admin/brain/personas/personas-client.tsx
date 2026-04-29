"use client";

import type { ReactNode } from "react";
import { createContext, lazy, useContext, useMemo } from "react";

import { TabbedPageShellNext, type TabbedShellTabDef } from "@/components/layout/TabbedPageShellNext";

import type { PersonasPageInitial } from "./personas-types";

const PersonasTab = lazy(() => import("./tabs/personas-tab").then((m) => ({ default: m.PersonasTab })));
const CostTab = lazy(() => import("./tabs/cost-tab").then((m) => ({ default: m.CostTab })));
const RoutingTab = lazy(() => import("./tabs/routing-tab").then((m) => ({ default: m.RoutingTab })));
const ActivityTab = lazy(() => import("./tabs/activity-tab").then((m) => ({ default: m.ActivityTab })));
const ModelRegistryTab = lazy(() =>
  import("./tabs/model-registry-tab").then((m) => ({ default: m.ModelRegistryTab })),
);

const PersonasInitialContext = createContext<PersonasPageInitial | null>(null);

export function usePersonasInitial(): PersonasPageInitial {
  const v = useContext(PersonasInitialContext);
  if (!v) {
    throw new Error("usePersonasInitial must be used within PersonasPageClient");
  }
  return v;
}

const TAB_DEFS: TabbedShellTabDef<
  "personas" | "cost" | "routing" | "activity" | "model-registry"
>[] = [
  { id: "personas", label: "Personas", Content: PersonasTab },
  { id: "cost", label: "Cost", Content: CostTab },
  { id: "routing", label: "Routing", Content: RoutingTab },
  { id: "activity", label: "Activity", Content: ActivityTab },
  { id: "model-registry", label: "Model Registry", Content: ModelRegistryTab },
];

export function PersonasPageClient(props: { initial: PersonasPageInitial; children?: ReactNode }) {
  const { initial } = props;
  const tabs = useMemo(() => TAB_DEFS, []);

  return (
    <PersonasInitialContext.Provider value={initial}>
      <div className="space-y-6 text-zinc-200">
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Brain Personas</h1>
          <p className="max-w-3xl text-sm text-zinc-400">
            Cursor rule personas, routing tables, cost telemetry, recent invocations, and the live model registry.
          </p>
        </header>
        {props.children}
        <TabbedPageShellNext tabs={tabs} defaultTab="personas" />
      </div>
    </PersonasInitialContext.Provider>
  );
}
