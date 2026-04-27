import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  BarChart2,
  ClipboardList,
  Command,
  Compass,
  FlaskConical,
  Globe,
  Home,
  LayoutGrid,
  List,
  Menu,
  PieChart,
  Receipt,
  Settings,
  Sparkles,
  Target,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";

import { useAccountContext } from '../../context/AccountContext';
import { useAuth } from '../../context/AuthContext';
import { isPlatformAdminRole } from '../../utils/userRole';
import AppDivider from '../ui/AppDivider';
import AppLogo from '../ui/AppLogo';
import useAdminHealth from '../../hooks/useAdminHealth';
import { useAccountBalances } from '@/hooks/usePortfolio';
import TopBarAccountSelector from './TopBarAccountSelector';
import SidebarStatusDot from './SidebarStatusDot';
import { ChatProvider } from '@/components/chat/ChatProvider';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { openCommandPalette } from '@/components/cmdk/openCommandPalette';
import { isTypingTarget } from '@/components/cmdk/CommandPalette';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { formatUserDisplayName } from '@/utils/userDisplayName';

const SIDEBAR_OPEN_STORAGE_KEY = 'qm.ui.sidebar_open';
const LAST_ROUTE_STORAGE_KEY = 'qm.ui.last_route';

const MD_UP = '(min-width: 48em)';

function useMediaQueryMinWidth(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return true;
    return window.matchMedia(query).matches;
  });
  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = () => setMatches(mql.matches);
    mql.addEventListener('change', handler);
    handler();
    return () => mql.removeEventListener('change', handler);
  }, [query]);
  return matches;
}

// ── Nav data model ──────────────────────────────────────────────────────────
//
// Sections climb the tier ladder: free-for-all at the top (TODAY, PORTFOLIO),
// Pro in the middle (SIGNALS, MARKETS), Pro+ at the bottom (LAB), then the
// universal SETTINGS rail. Chips are purely informational — click-through is
// never gated at the sidebar, the underlying page handles upsell.

type TierChip = 'pro' | 'pro_plus';

type NavItem = {
  label: string;
  icon: LucideIcon;
  path: string;
};

type NavSection = {
  id: string;
  title: string;
  items: readonly NavItem[];
  tier?: TierChip;
  /** Hide the whole section when this returns false. */
  visible?: (ctx: { isAdmin: boolean; portfolioNavVisible: boolean }) => boolean;
};

/**
 * Section-level tier chip classes. Muted enough to feel informational, not
 * pushy — aim is to communicate "this cluster graduates you to a paid tier"
 * without stamping a lock icon on every row.
 */
const TIER_CHIP_STYLES: Record<TierChip, { chipClass: string; label: string; srLabel: string }> = {
  pro: {
    // Amber / gold — low-sat background + darker amber foreground. Works
    // in both themes because Tailwind `amber-*/**` is token-friendly.
    chipClass:
      'border border-amber-400/30 bg-amber-400/10 text-amber-700 dark:text-amber-300',
    label: 'Pro',
    srLabel: 'Pro tier',
  },
  pro_plus: {
    // Violet — distinct enough from amber to signal a different tier at
    // a glance without raising visual weight.
    chipClass:
      'border border-violet-400/30 bg-violet-400/10 text-violet-700 dark:text-violet-300',
    label: 'Pro+',
    srLabel: 'Pro Plus tier',
  },
};

const TODAY_ITEMS: readonly NavItem[] = [
  { label: 'Home', icon: Home, path: '/' },
  { label: "Today's Cards", icon: ClipboardList, path: '/trade-cards/today' },
];

// Wave B capped each section at 4 items. PORTFOLIO graduates to 5 here
// because the founder called out Tax Center as a quarterly-use destination
// (LT/ST lot separation, tax-loss harvesting) — too rich to demote to a
// sub-tab, too important to hide in a command-palette-only entry. The
// 4-item guideline tolerates a 5th row when the slot is a demonstrably
// used primary feature; see the PR body for the rationale.
const PORTFOLIO_ITEMS: readonly NavItem[] = [
  { label: 'Overview', icon: PieChart, path: '/portfolio' },
  { label: 'Positions', icon: Wallet, path: '/portfolio/positions' },
  { label: 'Activity', icon: Activity, path: '/portfolio/activity' },
  { label: 'Tax Center', icon: Receipt, path: '/portfolio/tax' },
  { label: 'Workspace', icon: LayoutGrid, path: '/market/workspace' },
];

const SIGNALS_ITEMS: readonly NavItem[] = [
  { label: 'Candidates', icon: Sparkles, path: '/signals/candidates' },
  { label: 'Picks', icon: TrendingUp, path: '/signals/picks' },
  { label: 'Regime', icon: Compass, path: '/signals/regime' },
];

const MARKETS_ITEMS: readonly NavItem[] = [
  { label: 'Markets', icon: BarChart2, path: '/market' },
  { label: 'Universe', icon: Globe, path: '/market/universe' },
];

const LAB_ITEMS: readonly NavItem[] = [
  { label: 'Strategies', icon: Target, path: '/strategies' },
  { label: 'Backtest', icon: Activity, path: '/lab/monte-carlo' },
  { label: 'Walk-Forward', icon: List, path: '/lab/walk-forward' },
  { label: 'Shadow (paper)', icon: FlaskConical, path: '/shadow-trades' },
];

const SETTINGS_ITEMS: readonly NavItem[] = [
  { label: 'Settings', icon: Settings, path: '/settings' },
];

const NAV_SECTIONS: readonly NavSection[] = [
  { id: 'today', title: 'TODAY', items: TODAY_ITEMS },
  {
    id: 'portfolio',
    title: 'PORTFOLIO',
    items: PORTFOLIO_ITEMS,
    visible: ({ portfolioNavVisible }) => portfolioNavVisible,
  },
  { id: 'signals', title: 'SIGNALS', items: SIGNALS_ITEMS, tier: 'pro' },
  { id: 'markets', title: 'MARKETS', items: MARKETS_ITEMS, tier: 'pro' },
  { id: 'lab', title: 'LAB', items: LAB_ITEMS, tier: 'pro_plus' },
  { id: 'settings', title: 'SETTINGS', items: SETTINGS_ITEMS },
];

interface NavItemProps {
  icon: LucideIcon;
  label: string;
  path: string;
  isActive: boolean;
  onClick: () => void;
  badge?: number;
  showLabel?: boolean;
}

const NavItemButton: React.FC<NavItemProps> = React.memo(
  ({ icon: Icon, label, path, isActive, onClick, badge, showLabel = true }) => (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        'relative h-auto w-full rounded-lg py-2.5 font-medium transition-colors',
        showLabel ? 'justify-start px-4 text-left' : 'justify-center px-2',
        showLabel && isActive && 'border-l-2 border-primary bg-muted text-foreground',
        showLabel && !isActive && 'border-l-2 border-transparent text-muted-foreground hover:bg-muted/80 hover:text-foreground',
        !showLabel && isActive && 'bg-muted text-foreground',
        !showLabel && !isActive && 'text-muted-foreground hover:bg-muted/80 hover:text-foreground',
      )}
      aria-current={isActive ? 'page' : undefined}
      onClick={onClick}
      data-nav-path={path}
      data-active={isActive ? 'true' : 'false'}
    >
      <Icon className="size-[17px] shrink-0" strokeWidth={2} />
      {showLabel ? <span className="ml-3 text-sm">{label}</span> : null}
      {badge && badge > 0 ? (
        <Badge
          variant="destructive"
          className="ml-auto min-h-5 min-w-5 shrink-0 rounded-full px-1.5 text-[10px]"
        >
          {badge > 99 ? '99+' : badge}
        </Badge>
      ) : null}
    </Button>
  ),
);
NavItemButton.displayName = 'NavItemButton';

interface TierChipProps {
  tier: TierChip;
}

const TierChipBadge: React.FC<TierChipProps> = React.memo(({ tier }) => {
  const { chipClass, label, srLabel } = TIER_CHIP_STYLES[tier];
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-px',
        'text-[10px] font-medium uppercase tracking-wide',
        chipClass,
      )}
      aria-label={srLabel}
      data-tier-chip={tier}
    >
      {label}
    </span>
  );
});
TierChipBadge.displayName = 'TierChipBadge';

const DashboardLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { accounts } = useAccountContext();
  const { user, logout } = useAuth();
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    try {
      const raw = window.localStorage.getItem(SIDEBAR_OPEN_STORAGE_KEY);
      if (raw === null) return true;
      return raw === '1';
    } catch {
      return true;
    }
  });
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const isDesktop = useMediaQueryMinWidth(MD_UP);
  const cmdKLabel = useMemo(() => {
    if (typeof navigator === 'undefined') return 'Ctrl+K';
    return /Mac|iPhone|iPad|iPod/.test(navigator.userAgent) ? '⌘K' : 'Ctrl+K';
  }, []);

  const commaShortcutLabel = useMemo(() => {
    if (typeof navigator === 'undefined') return 'Ctrl+,';
    return /Mac|iPhone|iPad|iPod/.test(navigator.userAgent) ? '⌘,' : 'Ctrl+,';
  }, []);

  const balancesQuery = useAccountBalances();
  const hasBrokers = Boolean(balancesQuery.data && balancesQuery.data.length > 0);
  const isAdmin = isPlatformAdminRole(user?.role);
  const portfolioNavVisible = isAdmin || hasBrokers;

  const { health: adminHealth, loading: healthLoading } = useAdminHealth();
  const healthStatus = adminHealth?.composite_status ?? 'red';
  const healthReason = adminHealth?.composite_reason ?? 'Checking system health...';
  const healthDotClass =
    healthStatus === 'green'
      ? 'bg-[rgb(var(--status-success))]'
      : healthStatus === 'yellow'
        ? 'bg-[rgb(var(--status-warning))]'
        : 'bg-[rgb(var(--status-danger))]';

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_OPEN_STORAGE_KEY, isSidebarOpen ? '1' : '0');
    } catch {
      // ignore storage errors
    }
  }, [isSidebarOpen]);

  useEffect(() => {
    try {
      const fullPath = `${location.pathname}${location.search || ''}${location.hash || ''}`;
      window.localStorage.setItem(LAST_ROUTE_STORAGE_KEY, fullPath);
    } catch {
      // ignore storage errors
    }
  }, [location.hash, location.pathname, location.search]);

  // Cmd+, is a role-aware power shortcut: admins hop to the system-status
  // page they live in; everyone else lands on Connections, the surface
  // non-admins most often want to reach fast. The avatar "Settings" entry
  // stays aimed at /settings/profile (muscle memory) even though the
  // shortcut jumps elsewhere.
  const commaShortcutTarget = isAdmin ? '/settings/admin/system' : '/settings/connections';
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key !== ',' && e.code !== 'Comma') return;
      if (isTypingTarget(e.target)) return;
      e.preventDefault();
      navigate(commaShortcutTarget);
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [navigate, commaShortcutTarget]);

  const sidebarWidthClass = isSidebarOpen ? 'w-64' : 'w-16';

  const isPathActive = useCallback(
    (itemPath: string) => {
      const currentPath = location.pathname || '/';
      const params = new URLSearchParams(location.search);
      if (itemPath === '/') {
        return currentPath === '/';
      }
      if (itemPath === '/market') {
        if (currentPath === '/market') return true;
        if (currentPath.startsWith('/market/tracked')) return false;
        if (currentPath.startsWith('/market/scanner')) return false;
        if (currentPath.startsWith('/market/universe')) return false;
        if (currentPath.startsWith('/market/workspace')) return false;
        return currentPath.startsWith('/market/');
      }
      if (itemPath === '/market/universe') {
        // The Universe hub absorbed the former /market/tracked and
        // /market/scanner entries — keep the nav item lit on any of them.
        return (
          currentPath === '/market/universe' ||
          currentPath.startsWith('/market/universe/') ||
          currentPath.startsWith('/market/tracked') ||
          currentPath.startsWith('/market/scanner')
        );
      }
      if (itemPath === '/market/workspace') {
        return (
          currentPath === '/market/workspace' ||
          currentPath.startsWith('/market/workspace/') ||
          currentPath === '/portfolio/workspace' ||
          currentPath.startsWith('/portfolio/workspace/')
        );
      }
      if (itemPath === '/portfolio') {
        const tab = params.get('tab');
        return currentPath === '/portfolio' && (!tab || tab === 'overview');
      }
      if (itemPath === '/portfolio/positions') {
        return (
          currentPath === '/portfolio/positions' ||
          currentPath.startsWith('/portfolio/positions/') ||
          currentPath === '/portfolio/holdings' ||
          currentPath.startsWith('/portfolio/holdings/') ||
          currentPath === '/portfolio/options' ||
          currentPath.startsWith('/portfolio/options/') ||
          currentPath === '/portfolio/tax' ||
          currentPath.startsWith('/portfolio/tax/')
        );
      }
      if (itemPath === '/portfolio/activity') {
        return (
          currentPath === '/portfolio/activity' ||
          currentPath.startsWith('/portfolio/activity/') ||
          currentPath === '/portfolio/orders' ||
          currentPath.startsWith('/portfolio/orders/') ||
          currentPath === '/portfolio/transactions' ||
          currentPath.startsWith('/portfolio/transactions/') ||
          currentPath === '/portfolio/income' ||
          currentPath.startsWith('/portfolio/income/')
        );
      }
      if (itemPath === '/settings') {
        return currentPath === '/settings' || currentPath.startsWith('/settings/');
      }
      return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
    },
    [location.pathname, location.search],
  );

  const renderSectionHeader = (section: NavSection, sectionIndex: number, showLabel: boolean) => {
    if (!showLabel) return null;
    const chip = section.tier ? <TierChipBadge tier={section.tier} /> : null;
    const dot = section.id === 'settings' ? <SidebarStatusDot isAdmin={isAdmin} /> : null;
    return (
      <div
        className={cn(
          'mb-1.5 flex items-center gap-2 px-4',
          sectionIndex > 0 && 'mt-4',
        )}
      >
        <p className="text-[10px] font-semibold tracking-[0.08em] text-muted-foreground uppercase">
          {section.title}
        </p>
        {chip}
        {dot}
      </div>
    );
  };

  const renderSection = (section: NavSection, sectionIndex: number, showLabel: boolean) => (
    <div data-testid={`nav-section-${section.id}`} data-section-id={section.id}>
      {renderSectionHeader(section, sectionIndex, showLabel)}
      <div className="flex flex-col gap-1">
        {section.items.map((item) => {
          const active = isPathActive(item.path);
          return (
            <NavItemButton
              key={item.path}
              icon={item.icon}
              label={item.label}
              path={item.path}
              isActive={active}
              onClick={() => {
                navigate(item.path);
                setIsMobileNavOpen(false);
              }}
              showLabel={showLabel}
            />
          );
        })}
      </div>
    </div>
  );

  const renderNav = (opts: { showLabel: boolean; pxClass: string }) => {
    let idx = 0;
    return (
      <div className={cn('flex flex-col gap-2 py-4', opts.pxClass)}>
        {NAV_SECTIONS.map((section) => {
          if (section.visible && !section.visible({ isAdmin, portfolioNavVisible })) {
            return null;
          }
          const el = renderSection(section, idx, opts.showLabel);
          idx += 1;
          return <React.Fragment key={section.id}>{el}</React.Fragment>;
        })}
      </div>
    );
  };

  const sidebarShell = (opts: { showLabel: boolean; pxClass: string; showMenuToggle: boolean }) => (
    <div className="flex h-full min-h-0 flex-col bg-sidebar text-sidebar-foreground">
      <div
        className={cn(
          'flex shrink-0 items-center border-b border-border py-4',
          opts.showLabel ? 'justify-start px-5' : 'justify-center px-3',
        )}
      >
        {opts.showLabel ? (
          <Link
            to="/"
            aria-label="AxiomFolio home"
            className={cn(
              'flex items-center gap-2.5 rounded-sm',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar',
            )}
          >
            <AppLogo size={52} />
            <span className="text-base font-semibold tracking-tight text-foreground">AxiomFolio</span>
          </Link>
        ) : null}
        {opts.showMenuToggle ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Expand or collapse sidebar"
                className={cn('shrink-0 text-foreground', opts.showLabel && 'ml-auto')}
                onClick={() => setIsSidebarOpen((v) => !v)}
              >
                <Menu className="size-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              {opts.showLabel ? 'Collapse sidebar' : 'Expand sidebar'}
            </TooltipContent>
          </Tooltip>
        ) : null}
      </div>
      {opts.showLabel ? <AppDivider /> : null}
      <div className="min-h-0 flex-1 overflow-y-auto">{renderNav(opts)}</div>
    </div>
  );

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-screen w-screen overflow-hidden bg-background">
        {isDesktop ? (
          <aside
            className={cn(
              'flex h-screen shrink-0 flex-col overflow-y-auto border-r border-border transition-[width] duration-200 ease-out',
              sidebarWidthClass,
            )}
          >
            {sidebarShell({
              showLabel: isSidebarOpen,
              pxClass: isSidebarOpen ? 'px-4' : 'px-2',
              showMenuToggle: true,
            })}
          </aside>
        ) : null}

        {!isDesktop ? (
          <Dialog.Root open={isMobileNavOpen} onOpenChange={setIsMobileNavOpen}>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
              <Dialog.Content
                className="fixed top-0 left-0 z-50 flex h-screen w-[280px] max-w-[80vw] flex-col border-r border-border bg-sidebar p-0 shadow-lg outline-none data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left-2 data-[state=open]:animate-in data-[state=open]:slide-in-from-left-2"
                onPointerDownOutside={() => setIsMobileNavOpen(false)}
                onEscapeKeyDown={() => setIsMobileNavOpen(false)}
              >
                <Dialog.Title className="border-b border-border px-4 py-3 font-heading text-base font-semibold text-foreground">
                  AxiomFolio
                </Dialog.Title>
                <Dialog.Description className="sr-only">
                  Application sections and links
                </Dialog.Description>
                {sidebarShell({ showLabel: true, pxClass: 'px-4', showMenuToggle: false })}
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        ) : null}

        <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-[rgb(var(--bg-header))] px-6">
            <div className="flex items-center gap-4">
              {isDesktop && !isSidebarOpen ? (
                <Link
                  to="/"
                  aria-label="AxiomFolio home"
                  className={cn(
                    'flex items-center gap-2.5 rounded-sm',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-[rgb(var(--bg-header))]',
                  )}
                >
                  <AppLogo size={36} />
                  <span className="text-base font-semibold tracking-tight text-foreground">AxiomFolio</span>
                </Link>
              ) : null}
              {!isDesktop ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="Open navigation menu"
                      className="relative z-[2] text-foreground"
                      onClick={() => setIsMobileNavOpen(true)}
                    >
                      <Menu className="size-5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="text-xs">
                    Open menu
                  </TooltipContent>
                </Tooltip>
              ) : null}
              {portfolioNavVisible && accounts.length > 0 ? (
                <TopBarAccountSelector compact={!isDesktop} />
              ) : null}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className={cn(
                      'h-8 gap-1.5 px-2.5 font-sans text-xs',
                      'border-transparent bg-muted/70 hover:bg-muted',
                      'focus-visible:ring-2 focus-visible:ring-ring',
                    )}
                    aria-label="Open command palette"
                    onClick={() => openCommandPalette()}
                  >
                    <Command className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                    <kbd className="pointer-events-none inline-flex min-h-5 items-center rounded border border-border bg-background/80 px-1.5 font-mono text-[10px] font-medium tabular-nums text-foreground">
                      {cmdKLabel}
                    </kbd>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                  Command Palette ({cmdKLabel})
                </TooltipContent>
              </Tooltip>
            </div>

            <div className="flex items-center gap-4">
              {isAdmin && !healthLoading && adminHealth ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="System Health"
                      className="relative text-foreground"
                      onClick={() => navigate('/settings/admin/system')}
                    >
                      <Activity className="size-5" />
                      <span
                        className={cn(
                          'absolute top-1.5 right-1.5 size-2.5 rounded-full border-2 border-[rgb(var(--bg-header))]',
                          healthDotClass,
                        )}
                      />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-[240px] text-xs">
                    {healthReason}
                  </TooltipContent>
                </Tooltip>
              ) : null}

              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <Button type="button" variant="ghost" size="sm" className="gap-2 px-2 font-normal">
                    <span className="flex size-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                      {formatUserDisplayName(user).slice(0, 1).toUpperCase()}
                    </span>
                    <span className="text-sm">{formatUserDisplayName(user)}</span>
                  </Button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    align="end"
                    sideOffset={8}
                    className={cn(
                      'z-50 min-w-[240px] rounded-xl border border-border bg-popover p-2 text-popover-foreground shadow-md',
                      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2',
                    )}
                  >
                    <div className="px-2 py-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">Account</p>
                      <p className="mt-1 text-sm font-semibold">{formatUserDisplayName(user)}</p>
                    </div>
                    <AppDivider />
                    <DropdownMenu.Item
                      className="cursor-default rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                      onSelect={() => navigate('/settings/profile')}
                    >
                      Profile
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="flex cursor-default items-center gap-2 rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                      onSelect={() => navigate('/settings/profile')}
                    >
                      <span>Settings</span>
                      <kbd className="ml-auto inline-flex min-h-5 items-center rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium tabular-nums text-muted-foreground">
                        {commaShortcutLabel}
                      </kbd>
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="cursor-default rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                      onSelect={() => navigate('/settings/preferences')}
                    >
                      Preferences
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="cursor-default rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                      onSelect={() => navigate('/pricing')}
                    >
                      Pricing
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="cursor-default rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                      onSelect={() => navigate('/settings/connections')}
                    >
                      Connections
                    </DropdownMenu.Item>
                    {isAdmin ? (
                      <DropdownMenu.Item
                        className="cursor-default rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                        onSelect={() => navigate('/settings/admin/system')}
                      >
                        System Status
                      </DropdownMenu.Item>
                    ) : null}
                    <AppDivider />
                    <DropdownMenu.Item
                      className="cursor-default rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                      onSelect={() => {
                        logout();
                        navigate('/login');
                      }}
                    >
                      Logout
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
          </header>

          <ChatProvider>
            <main className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-4">
              <Outlet />
            </main>
            <footer className="shrink-0 border-t border-border px-4 py-2.5 text-center">
              <Link
                to="/why-free"
                className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
              >
                Why is this free?
              </Link>
            </footer>
            {isAdmin && <ChatBubble />}
          </ChatProvider>
        </div>
      </div>
    </TooltipProvider>
  );
};

export default DashboardLayout;
