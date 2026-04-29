"use client";

import { lazy } from "react";

import {
  TabbedPageShellNext,
  type TabbedShellTabDefNext,
} from "@/components/layout/TabbedPageShellNext";

export type SelfImprovementTabId =
  | "index"
  | "learning"
  | "promotions"
  | "outcomes"
  | "retros"
  | "automation-state"
  | "procedural-memory";

const IndexTab = lazy(async () => {
  const { IndexTab: C } = await import("./tabs/index-tab");
  return { default: C };
});
const LearningTab = lazy(async () => {
  const { LearningTab: C } = await import("./tabs/learning-tab");
  return { default: C };
});
const PromotionsTab = lazy(async () => {
  const { PromotionsTab: C } = await import("./tabs/promotions-tab");
  return { default: C };
});
const OutcomesTab = lazy(async () => {
  const { OutcomesTab: C } = await import("./tabs/outcomes-tab");
  return { default: C };
});
const RetrosTab = lazy(async () => {
  const { RetrosTab: C } = await import("./tabs/retros-tab");
  return { default: C };
});
const AutomationStateTab = lazy(async () => {
  const { AutomationStateTab: C } = await import("./tabs/automation-state-tab");
  return { default: C };
});
const ProceduralMemoryTab = lazy(async () => {
  const { ProceduralMemoryTab: C } = await import("./tabs/procedural-memory-tab");
  return { default: C };
});

const TABS: readonly TabbedShellTabDefNext<SelfImprovementTabId>[] = [
  { id: "index", label: "Overview", Content: IndexTab },
  { id: "learning", label: "Learning", Content: LearningTab },
  { id: "promotions", label: "Promotions", Content: PromotionsTab },
  { id: "outcomes", label: "Outcomes", Content: OutcomesTab },
  { id: "retros", label: "Retros", Content: RetrosTab },
  { id: "automation-state", label: "Automation", Content: AutomationStateTab },
  { id: "procedural-memory", label: "Procedural memory", Content: ProceduralMemoryTab },
];

export function SelfImprovementClient() {
  return (
    <TabbedPageShellNext
      tabs={TABS}
      defaultTab="index"
      basePath="/admin/brain/self-improvement"
      paramKey="tab"
    />
  );
}
