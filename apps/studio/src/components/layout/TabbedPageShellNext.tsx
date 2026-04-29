"use client";

import { lazy, useCallback, useMemo, type LazyExoticComponent, type ComponentType, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  TabbedPageShell as BaseTabbedPageShell,
  type TabbedShellTabDef,
} from "@paperwork-labs/ui";

/**
 * Tab definition for studio pages. Accepts either:
 * - `Content`: a React.LazyExoticComponent (preferred, matches `@paperwork-labs/ui`)
 * - `content`: a ReactNode (eager, for simple scaffold pages)
 *
 * The shell wraps `content` in a tiny lazy adapter so the underlying primitive
 * always sees a Content component.
 */
export type StudioTabDef<T extends string> = {
  id: T;
  label: string;
  Content?: LazyExoticComponent<ComponentType>;
  content?: ReactNode;
};

export type TabbedPageShellNextProps<T extends string> = {
  tabs: readonly StudioTabDef<T>[];
  defaultTab: T;
  paramKey?: string;
  className?: string;
  tabsListClassName?: string;
  endAdornment?: ReactNode;
};

function adaptTab<T extends string>(t: StudioTabDef<T>): TabbedShellTabDef<T> {
  if (t.Content) {
    return { id: t.id, label: t.label, Content: t.Content };
  }
  const node = t.content ?? null;
  const Adapter = lazy(async () => ({
    default: () => <>{node}</>,
  }));
  return { id: t.id, label: t.label, Content: Adapter };
}

export function TabbedPageShell<T extends string>(props: TabbedPageShellNextProps<T>) {
  const { tabs, defaultTab, paramKey = "tab", ...rest } = props;
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const fromUrl = searchParams.get(paramKey);
  const allowedIds = tabs.map((t) => t.id);
  const activeTab = (allowedIds.includes(fromUrl as T) ? (fromUrl as T) : defaultTab) as T;

  const adaptedTabs = useMemo(() => tabs.map((t) => adaptTab(t)), [tabs]);

  const onTabChange = useCallback(
    (tab: T) => {
      const next = new URLSearchParams(searchParams.toString());
      next.set(paramKey, tab);
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams, paramKey],
  );

  return (
    <BaseTabbedPageShell
      {...rest}
      tabs={adaptedTabs}
      defaultTab={defaultTab}
      activeTab={activeTab}
      onTabChange={onTabChange}
    />
  );
}

export { useActiveTab } from "@paperwork-labs/ui";
export type { TabbedShellTabDef };
