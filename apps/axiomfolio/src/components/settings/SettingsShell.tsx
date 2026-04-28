"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bell,
  ChevronRight,
  ClipboardList,
  Cpu,
  Database,
  KeyRound,
  Link2,
  Lock,
  ShieldAlert,
  Sliders,
  User,
  type LucideIcon,
} from "lucide-react";

import { useBackendUser } from "@/hooks/use-backend-user";
import { isPlatformAdminRole } from "@/utils/userRole";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type SettingsLink = {
  to: string;
  label: string;
  icon: LucideIcon;
};

type SettingsCluster = {
  id: string;
  label: string;
  items: readonly SettingsLink[];
  adminOnly?: boolean;
};

const CLUSTERS: readonly SettingsCluster[] = [
  {
    id: "account",
    label: "Account",
    items: [
      { to: "/settings/profile", label: "Profile", icon: User },
      { to: "/settings/preferences", label: "Preferences", icon: Sliders },
      { to: "/settings/notifications", label: "Notifications", icon: Bell },
    ],
  },
  {
    id: "connections",
    label: "Connections",
    items: [
      { to: "/settings/connections", label: "Brokers", icon: Link2 },
      {
        to: "/settings/connections/historical-import",
        label: "Historical import",
        icon: Database,
      },
    ],
  },
  {
    id: "trading",
    label: "Trading",
    items: [
      { to: "/settings/account-risk", label: "Account risk", icon: ShieldAlert },
    ],
  },
  {
    id: "ai",
    label: "AI",
    items: [
      { to: "/settings/ai-keys", label: "AI keys", icon: KeyRound },
      { to: "/settings/mcp", label: "MCP tokens", icon: KeyRound },
    ],
  },
  {
    id: "privacy",
    label: "Privacy",
    items: [{ to: "/settings/data-privacy", label: "Data privacy", icon: Lock }],
  },
  {
    id: "admin",
    label: "Admin",
    adminOnly: true,
    items: [
      { to: "/system-status", label: "System Status", icon: Activity },
      { to: "/settings/users", label: "Users", icon: User },
      { to: "/settings/admin/agent", label: "Agent", icon: Cpu },
      { to: "/settings/admin/picks", label: "Picks validator", icon: ClipboardList },
    ],
  },
];

function MenuLink({ to, children }: { to: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const isActive = pathname === to;

  return (
    <Link href={to} className="block no-underline" scroll={false}>
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
    </Link>
  );
}

function SettingsIconLink({ to, label, Icon }: { to: string; label: string; Icon: LucideIcon }) {
  const pathname = usePathname();
  const isActive = pathname === to;

  return (
    <Link href={to} className="no-underline" scroll={false}>
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
    </Link>
  );
}

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

function SettingsBreadcrumb({ clusters }: { clusters: readonly SettingsCluster[] }) {
  const pathname = usePathname();
  const crumb = resolveBreadcrumb(pathname, clusters);
  return (
    <nav
      aria-label="Settings breadcrumb"
      className="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground"
      data-testid="settings-breadcrumb"
    >
      <Link href="/settings/profile" className="hover:text-foreground">
        Settings
      </Link>
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

export default function SettingsShell({ children }: { children: React.ReactNode }) {
  const { user } = useBackendUser();
  const isAdmin = isPlatformAdminRole(user?.role);
  const [isDesktop, setIsDesktop] = React.useState(
    typeof window !== "undefined" ? window.matchMedia("(min-width: 48em)").matches : true,
  );

  React.useEffect(() => {
    const mq = window.matchMedia("(min-width: 48em)");
    const handler = () => setIsDesktop(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const visibleClusters = CLUSTERS.filter((c) => !c.adminOnly || isAdmin);

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
                        <MenuLink key={item.to} to={item.to}>
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
                      label={item.label}
                      Icon={item.icon}
                    />
                  )),
                )}
              </nav>
            )}
            <div className="min-w-0 flex-1 overflow-x-hidden">
              <SettingsBreadcrumb clusters={CLUSTERS} />
              {children}
            </div>
          </div>
        </TooltipProvider>
      </div>
    </div>
  );
}
