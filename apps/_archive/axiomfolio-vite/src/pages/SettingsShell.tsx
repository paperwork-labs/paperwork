import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
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
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { isPlatformAdminRole } from '../utils/userRole';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

// ── Cluster model ──────────────────────────────────────────────────────────
//
// Flat rail replaced by seven clusters. Order reflects expected frequency of
// use, not alphabetical (Account → Connections → Trading → Notifications →
// AI → Privacy → Admin). Admin is the founder's most-visited cluster, so
// within Admin the first entry is System Status (per founder feedback —
// "founder only checks in on system status often"). Keeps the study in
// docs/plans/SETTINGS_NAV_STUDY_2026Q2.md in lockstep with the code.

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
    id: 'account',
    label: 'Account',
    items: [
      { to: '/settings/profile', label: 'Profile', icon: User },
      { to: '/settings/preferences', label: 'Preferences', icon: Sliders },
      { to: '/settings/notifications', label: 'Notifications', icon: Bell },
    ],
  },
  {
    id: 'connections',
    label: 'Connections',
    items: [
      { to: '/settings/connections', label: 'Brokers', icon: Link2 },
      {
        to: '/settings/connections/historical-import',
        label: 'Historical import',
        icon: Database,
      },
    ],
  },
  {
    id: 'trading',
    label: 'Trading',
    items: [
      { to: '/settings/trading/account-risk', label: 'Account risk', icon: ShieldAlert },
    ],
  },
  {
    id: 'ai',
    label: 'AI',
    items: [
      { to: '/settings/ai-keys', label: 'AI keys', icon: KeyRound },
      { to: '/settings/mcp', label: 'MCP tokens', icon: KeyRound },
    ],
  },
  {
    id: 'privacy',
    label: 'Privacy',
    items: [
      { to: '/settings/data-privacy', label: 'Data privacy', icon: Lock },
    ],
  },
  {
    id: 'admin',
    label: 'Admin',
    adminOnly: true,
    // Operator Actions + Pipeline + Health all live on the System Status
    // page today. The Admin cluster only exposes distinct routes, so the
    // founder-asked "Operator Actions / Pipeline / Health / Flags" are
    // folded into System Status rather than duplicating four links to the
    // same URL. When those pages split out we'll add them here.
    items: [
      // System Status is intentionally the first item — founder feedback:
      // "founder only checks in on system status often".
      { to: '/settings/admin/system', label: 'System Status', icon: Activity },
      { to: '/settings/admin/users', label: 'Users', icon: User },
      { to: '/settings/admin/agent', label: 'Agent', icon: Cpu },
      { to: '/settings/admin/picks', label: 'Picks validator', icon: ClipboardList },
    ],
  },
];

const MenuLink: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => (
  <NavLink to={to} end className="block no-underline">
    {({ isActive }) => (
      <Button
        type="button"
        variant="ghost"
        className={cn(
          'h-9 w-full justify-start rounded-md border-l-2 border-transparent px-3 font-medium transition-colors',
          isActive
            ? 'border-primary bg-muted text-foreground'
            : 'text-muted-foreground hover:bg-muted/80 hover:text-foreground',
        )}
      >
        {children}
      </Button>
    )}
  </NavLink>
);

// Resolve the current route to "Settings / <Cluster> / <Page>" for the
// breadcrumb row. Kept as a pure helper for testing.
function resolveBreadcrumb(
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

const SettingsBreadcrumb: React.FC<{ clusters: readonly SettingsCluster[] }> = ({ clusters }) => {
  const location = useLocation();
  const crumb = resolveBreadcrumb(location.pathname, clusters);
  return (
    <nav
      aria-label="Settings breadcrumb"
      className="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground"
      data-testid="settings-breadcrumb"
    >
      <NavLink to="/settings/profile" className="hover:text-foreground">
        Settings
      </NavLink>
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
};

const SettingsShell: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = isPlatformAdminRole(user?.role);
  const [isDesktop, setIsDesktop] = React.useState(
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 48em)').matches : true,
  );

  React.useEffect(() => {
    const mq = window.matchMedia('(min-width: 48em)');
    const handler = () => setIsDesktop(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const visibleClusters = CLUSTERS.filter((c) => !c.adminOnly || isAdmin);

  const iconNav = (to: string, label: string, Icon: LucideIcon) => (
    <NavLink to={to} end className="no-underline">
      {({ isActive }) => (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant={isActive ? 'default' : 'ghost'}
              className={cn(
                'h-auto w-full flex-col items-center justify-center gap-1 rounded-md px-1 py-2 text-[10px] font-medium',
                isActive
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
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
      )}
    </NavLink>
  );

  return (
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
                      'px-2 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase',
                      clusterIdx > 0 && 'mt-4',
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
              cluster.items.map((item) => iconNav(item.to, item.label, item.icon)),
            )}
          </nav>
        )}
        <div className="min-w-0 flex-1 overflow-x-hidden">
          <SettingsBreadcrumb clusters={CLUSTERS} />
          <Outlet />
        </div>
      </div>
    </TooltipProvider>
  );
};

export { resolveBreadcrumb };
export default SettingsShell;
