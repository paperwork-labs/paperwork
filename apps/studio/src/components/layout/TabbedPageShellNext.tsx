"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  TabbedPageShell as BaseTabbedPageShell,
  type TabbedPageShellProps as BaseProps,
  type TabbedShellTabDef,
} from "@paperwork-labs/ui";

export type TabbedPageShellNextProps<T extends string> = Omit<
  BaseProps<T>,
  "activeTab" | "onTabChange"
> & {
  paramKey?: string;
};

export function TabbedPageShell<T extends string>(props: TabbedPageShellNextProps<T>) {
  const { tabs, defaultTab, paramKey = "tab", ...rest } = props;
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const fromUrl = searchParams.get(paramKey);
  const allowedIds = tabs.map((t) => t.id);
  const activeTab = (allowedIds.includes(fromUrl as T) ? (fromUrl as T) : defaultTab) as T;

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
      tabs={tabs}
      defaultTab={defaultTab}
      activeTab={activeTab}
      onTabChange={onTabChange}
    />
  );
}

export { useActiveTab } from "@paperwork-labs/ui";
export type { TabbedShellTabDef };
