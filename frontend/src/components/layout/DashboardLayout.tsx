import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  BarChart2,
  BookOpen,
  Brain,
  CalendarDays,
  Compass,
  FileText,
  Gauge,
  Home,
  LayoutGrid,
  List,
  Menu,
  PieChart,
  Settings,
  Shield,
  ShoppingBag,
  Sparkles,
  Tag,
  Target,
  Layers,
  ClipboardList,
  Grid3x3,
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
import { CompactAccountSelector as AccountSelector } from '../shared/CompactAccountSelector';
import { ChatProvider } from '@/components/chat/ChatProvider';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

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

function displayName(user: { full_name?: string | null; username?: string } | null): string {
  // Display the stored name verbatim (trim-only). Global title-casing mangled
  // legitimate names like "McDonald" -> "Mcdonald" and "de la Rosa" ->
  // "De La Rosa". Respect whatever the user typed in Settings > Profile.
  if (!user) return 'Guest';
  const raw = (user.full_name?.trim() || user.username?.trim() || 'Guest').trim();
  return raw || 'Guest';
}

const portfolioItems = [
  { label: 'Overview', icon: PieChart, path: '/portfolio' },
  { label: 'Holdings', icon: List, path: '/portfolio/holdings' },
  { label: 'Options', icon: Layers, path: '/portfolio/options' },
  { label: 'Transactions', icon: FileText, path: '/portfolio/transactions' },
  { label: 'Categories', icon: Tag, path: '/portfolio/categories' },
  { label: 'Tax Center', icon: Shield, path: '/portfolio/tax' },
  { label: 'Orders', icon: ShoppingBag, path: '/portfolio/orders' },
  { label: 'Workspace', icon: LayoutGrid, path: '/portfolio/workspace' },
  { label: 'Allocation', icon: Grid3x3, path: '/portfolio/allocation' },
  { label: 'Income', icon: CalendarDays, path: '/portfolio/income' },
];

function buildSettingsItems(): { label: string; icon: typeof Settings; path: string }[] {
  return [{ label: 'Settings', icon: Settings, path: '/settings' }];
}

function buildMarketItems() {
  type Item = { label: string; icon: LucideIcon; path: string };
  const items: Item[] = [
    { label: 'Home', icon: Home, path: '/' },
    { label: 'Markets', icon: BarChart2, path: '/market' },
    { label: 'Tracked', icon: List, path: '/market/tracked' },
    { label: 'Strategies', icon: Target, path: '/lab/strategies' },
    { label: 'Backtest', icon: Activity, path: '/lab/monte-carlo' },
    { label: 'Intelligence', icon: Brain, path: '/lab/intelligence' },
    { label: 'Walk-Forward', icon: Activity, path: '/lab/walk-forward' },
    { label: 'Education', icon: BookOpen, path: '/learn/education' },
    { label: 'Candidates', icon: Sparkles, path: '/signals/candidates' },
    { label: 'Regime', icon: Gauge, path: '/signals/regime' },
    { label: 'Stage Scan', icon: Compass, path: '/signals/stage-scan' },
    { label: 'Picks', icon: ClipboardList, path: '/signals/picks' },
    { label: 'Today\'s Cards', icon: ClipboardList, path: '/trade-cards/today' },
  ];
  return items;
}

type MarketNavItem = { label: string; icon: LucideIcon; path: string };

interface NavItemProps {
  icon: LucideIcon;
  label: string;
  path: string;
  isActive: boolean;
  onClick: () => void;
  badge?: number;
  showLabel?: boolean;
}

const NavItem: React.FC<NavItemProps> = ({
  icon: Icon,
  label,
  path,
  isActive,
  onClick,
  badge,
  showLabel = true,
}) => (
  <Button
    type="button"
    variant="ghost"
    className={cn(
      'relative h-auto w-full rounded-lg py-2.5 font-medium transition-colors',
      showLabel ? 'justify-start px-4 text-left' : 'justify-center px-2',
      showLabel && isActive && 'border-l-2 border-primary bg-muted text-foreground',
      showLabel && !isActive && 'border-l-2 border-transparent text-muted-foreground hover:bg-muted/80 hover:text-foreground',
      !showLabel && isActive && 'bg-muted text-foreground',
      !showLabel && !isActive && 'text-muted-foreground hover:bg-muted/80 hover:text-foreground'
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
);

const DashboardLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { accounts, loading: accountsLoading, selected, setSelected } = useAccountContext();
  const { user, logout, appSettings, appSettingsReady } = useAuth();
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

  const openCommandPalette = useCallback(() => {
    const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    window.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'k',
        code: 'KeyK',
        metaKey: isMac,
        ctrlKey: !isMac,
        bubbles: true,
        cancelable: true,
      })
    );
  }, []);
  const marketOnly = appSettingsReady ? Boolean(appSettings?.market_only_mode) : true;
  const isAdmin = isPlatformAdminRole(user?.role);
  const portfolioEnabled = isAdmin || (!marketOnly && Boolean(appSettings?.portfolio_enabled));
  const marketItems = useMemo(() => buildMarketItems(), []);
  const settingsNavItems = useMemo(() => buildSettingsItems(), []);

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

  const sidebarWidthClass = isSidebarOpen ? 'w-64' : 'w-16';

  const isPathActive = useCallback(
    (itemPath: string) => {
      const currentPath = location.pathname || '/';
      if (itemPath === '/') {
        return currentPath === '/';
      }
      if (itemPath === '/market') {
        return currentPath === '/market' || currentPath.startsWith('/market/');
      }
      if (itemPath === '/portfolio') {
        return currentPath === '/portfolio';
      }
      return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
    },
    [location.pathname]
  );

  const renderSection = (
    title: string,
    items: MarketNavItem[] | typeof portfolioItems,
    showLabel: boolean,
    sectionIndex: number
  ) => (
    <div>
      {showLabel ? (
        <p
          className={cn(
            'mb-1.5 px-4 text-[10px] font-semibold tracking-[0.08em] text-muted-foreground uppercase',
            sectionIndex > 0 && 'mt-4'
          )}
        >
          {title}
        </p>
      ) : null}
      <div className="flex flex-col gap-1">
        {items.map((item) => {
          const active = isPathActive(item.path);
          return (
            <NavItem
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
    const next = () => idx++;
    return (
      <div className={cn('flex flex-col gap-2 py-4', opts.pxClass)}>
        {renderSection('MARKET', marketItems, opts.showLabel, next())}
        {portfolioEnabled ? renderSection('PORTFOLIO', portfolioItems, opts.showLabel, next()) : null}
        {isAdmin ? renderSection('SETTINGS', settingsNavItems, opts.showLabel, next()) : null}
      </div>
    );
  };

  const sidebarShell = (opts: { showLabel: boolean; pxClass: string; showMenuToggle: boolean }) => (
    <div className="flex h-full min-h-0 flex-col bg-sidebar text-sidebar-foreground">
      <div
        className={cn(
          'flex shrink-0 items-center border-b border-border py-4',
          opts.showLabel ? 'justify-start px-5' : 'justify-center px-3'
        )}
      >
        {opts.showLabel ? (
          <Link
            to="/"
            aria-label="AxiomFolio home"
            className={cn(
              'flex items-center gap-2.5 rounded-md',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar'
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
              sidebarWidthClass
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
                    'flex items-center gap-2.5 rounded-md',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-[rgb(var(--bg-header))]'
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
              {portfolioEnabled && accounts.length > 0 ? (
                <AccountSelector
                  value={selected}
                  onChange={setSelected}
                  disabled={accountsLoading}
                  accounts={accounts}
                  width={isDesktop ? '200px' : '180px'}
                />
              ) : null}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="hidden h-8 gap-1.5 px-2.5 font-sans text-xs sm:inline-flex"
                aria-label="Toggle command palette"
                onClick={openCommandPalette}
              >
                <span className="text-muted-foreground">Search</span>
                <kbd className="pointer-events-none inline-flex min-h-5 items-center rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-foreground">
                  {cmdKLabel}
                </kbd>
              </Button>
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
                          healthDotClass
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
                      {displayName(user).slice(0, 1).toUpperCase()}
                    </span>
                    <span className="text-sm">{displayName(user)}</span>
                  </Button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    align="end"
                    sideOffset={8}
                    className={cn(
                      'z-50 min-w-[240px] rounded-xl border border-border bg-popover p-2 text-popover-foreground shadow-md',
                      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2'
                    )}
                  >
                    <div className="px-2 py-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">Account</p>
                      <p className="mt-1 text-sm font-semibold">{displayName(user)}</p>
                    </div>
                    <AppDivider />
                    <DropdownMenu.Item
                      className="cursor-default rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground"
                      onSelect={() => navigate('/settings/profile')}
                    >
                      Profile
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
