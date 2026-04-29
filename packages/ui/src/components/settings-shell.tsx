"use client";

import * as React from "react";
import { ChevronRight, type LucideIcon } from "lucide-react";

import { cn } from "../lib/utils";
import { Button } from "./button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./tooltip";

export type SettingsLink = {
  to: string;
  label: string;
  icon: LucideIcon;
};

export type SettingsCluster = {
  id: string;
  label: string;
  items: readonly SettingsLink[];
  adminOnly?: boolean;
};

export type SettingsShellLinkComponent = React.ComponentType<{
  href: string;
  className?: string;
  scroll?: boolean;
  children: React.ReactNode;
}>;

export type SettingsShellProps = {
  children: React.ReactNode;
  clusters: readonly SettingsCluster[];
  /** Next.js `Link` or compatible router link. */
  LinkComponent: SettingsShellLinkComponent;
  /** Current pathname from host router (e.g. Next.js `usePathname()`). */
  pathname: string;
  /** Root path for the "Settings" crumb (default `/settings/profile`). */
  settingsHomeHref?: string;
  /** When omitted, `adminOnly` clusters are hidden. */
  useAdminGate?: () => boolean;
};

export function resolveBreadcrumb(
  pathname: string,
  clusters: readonly SettingsCluster[],
): { cluster: string; page: string } | null {
  for (const cluster of clusters) {
    for (const item of cluster.items) {
      if (pathname === item.to || pathname.startsWith(`${item.to}/`)) {
        return { cluster: cluster.label, page: item.label };
      }
    }
  }
  return null;
}

function MenuLink({
  to,
  pathname,
  children,
  LinkComponent,
}: {
  to: string;
  pathname: string;
  children: React.ReactNode;
  LinkComponent: SettingsShellLinkComponent;
}) {
  const isActive = pathname === to;

  return (
    <LinkComponent href={to} className="block no-underline" scroll={false}>
      <Button
        type="button"
        variant="ghost"
        className={cn(
          "h-9 w-full justify-start rounded-md border-l-2 border-transparent px-3 font-medium transition-colors",
          isActive
            ? "border-primary bg-muted text-foreground"
            : "text-muted-foreground hover:bg-muted/80 hover:text-foreground",
        )}
      >
        {children}
      </Button>
    </LinkComponent>
  );
}

function SettingsIconLink({
  to,
  pathname,
  label,
  Icon,
  LinkComponent,
}: {
  to: string;
  pathname: string;
  label: string;
  Icon: LucideIcon;
  LinkComponent: SettingsShellLinkComponent;
}) {
  const isActive = pathname === to;

  return (
    <LinkComponent href={to} className="no-underline" scroll={false}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant={isActive ? "default" : "ghost"}
            className={cn(
              "h-auto w-full flex-col items-center justify-center gap-1 rounded-md px-1 py-2 text-[10px] font-medium",
              isActive
                ? "bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
            aria-label={label}
          >
            <Icon className="size-4" aria-hidden />
            <span className="max-w-full truncate leading-tight">{label}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right" className="text-background">
          {label}
        </TooltipContent>
      </Tooltip>
    </LinkComponent>
  );
}

function SettingsBreadcrumb({
  pathname,
  resolveClusters,
  settingsHomeHref,
  LinkComponent,
}: {
  pathname: string;
  resolveClusters: readonly SettingsCluster[];
  settingsHomeHref: string;
  LinkComponent: SettingsShellLinkComponent;
}) {
  const crumb = resolveBreadcrumb(pathname, resolveClusters);
  return (
    <nav
      aria-label="Settings breadcrumb"
      className="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground"
      data-testid="settings-breadcrumb"
    >
      <LinkComponent href={settingsHomeHref} className="hover:text-foreground" scroll={false}>
        Settings
      </LinkComponent>
      {crumb ? (
        <>
          <ChevronRight className="size-3 shrink-0" aria-hidden />
          <span>{crumb.cluster}</span>
          <ChevronRight className="size-3 shrink-0" aria-hidden />
          <span className="text-foreground">{crumb.page}</span>
        </>
      ) : null}
    </nav>
  );
}

function readDesktopMatch(query: string): boolean {
  const mm = (globalThis as { matchMedia?: (q: string) => MediaQueryList }).matchMedia;
  if (typeof mm !== "function") return true;
  return mm(query).matches;
}

export function SettingsShell({
  children,
  clusters,
  LinkComponent,
  pathname,
  settingsHomeHref = "/settings/profile",
  useAdminGate,
}: SettingsShellProps) {
  const isAdmin = useAdminGate?.() ?? false;
  const [isDesktop, setIsDesktop] = React.useState(() => readDesktopMatch("(min-width: 48em)"));

  React.useEffect(() => {
    const mm = (globalThis as { matchMedia?: (q: string) => MediaQueryList }).matchMedia;
    if (typeof mm !== "function") return;
    const mq = mm("(min-width: 48em)");
    const handler = () => setIsDesktop(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const visibleClusters = React.useMemo(
    () => clusters.filter((c) => !c.adminOnly || isAdmin),
    [clusters, isAdmin],
  );

  return (
    <div className="min-h-0 w-full min-w-0">
      <div className="mx-auto w-full max-w-[1200px] px-4 py-6 md:px-6 md:py-8">
        <TooltipProvider delayDuration={200}>
          <div className="flex min-w-0 gap-2 overflow-x-hidden p-0">
            {isDesktop ? (
              <nav className="w-44 shrink-0" aria-label="Settings">
                <div className="flex flex-col gap-1">
                  {visibleClusters.map((cluster, clusterIdx) => (
                    <div
                      key={cluster.id}
                      data-testid={`settings-cluster-${cluster.id}`}
                      data-cluster-id={cluster.id}
                    >
                      <p
                        className={cn(
                          "px-2 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase",
                          clusterIdx > 0 && "mt-4",
                        )}
                      >
                        {cluster.label}
                      </p>
                      {cluster.items.map((item) => (
                        <MenuLink
                          key={item.to}
                          to={item.to}
                          pathname={pathname}
                          LinkComponent={LinkComponent}
                        >
                          {item.label}
                        </MenuLink>
                      ))}
                    </div>
                  ))}
                </div>
              </nav>
            ) : (
              <nav className="flex w-20 shrink-0 flex-col gap-1" aria-label="Settings">
                {visibleClusters.flatMap((cluster) =>
                  cluster.items.map((item) => (
                    <SettingsIconLink
                      key={item.to}
                      to={item.to}
                      pathname={pathname}
                      label={item.label}
                      Icon={item.icon}
                      LinkComponent={LinkComponent}
                    />
                  )),
                )}
              </nav>
            )}
            <div className="min-w-0 flex-1 overflow-x-hidden">
              <SettingsBreadcrumb
                pathname={pathname}
                resolveClusters={clusters}
                settingsHomeHref={settingsHomeHref}
                LinkComponent={LinkComponent}
              />
              {children}
            </div>
          </div>
        </TooltipProvider>
      </div>
    </div>
  );
}

export default SettingsShell;
