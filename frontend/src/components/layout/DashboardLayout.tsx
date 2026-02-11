import React, { useEffect, useState } from 'react';
import {
  Box,
  Flex,
  HStack,
  VStack,
  IconButton,
  Text,
  Badge,
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  MenuRoot,
  MenuTrigger,
  MenuContent,
  MenuItem,
  Button,
  useMediaQuery,
} from '@chakra-ui/react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  FiHome,
  FiActivity,
  FiList,
  FiPieChart,
  FiGrid,
  FiTag,
  FiFileText,
  FiTarget,
  FiSettings,
  FiMenu,
  FiSun,
  FiMoon,
  FiBell,
} from 'react-icons/fi';
import { FaBrain } from 'react-icons/fa';
import { portfolioApi } from '../../services/api';
import { useAccountContext } from '../../context/AccountContext';
import { useAuth } from '../../context/AuthContext';
import AppDivider from '../ui/AppDivider';

const SIDEBAR_OPEN_STORAGE_KEY = 'qm.ui.sidebar_open';
const LAST_ROUTE_STORAGE_KEY = 'qm.ui.last_route';

const marketItems = [
  { label: 'Dashboard', icon: FiHome, path: '/' },
  { label: 'Tracked', icon: FiList, path: '/market/tracked' },
  { label: 'Coverage', icon: FiActivity, path: '/market/coverage' },
];

const portfolioItems = [
  { label: 'Dashboard', icon: FiPieChart, path: '/portfolio' },
  { label: 'Workspace', icon: FiGrid, path: '/workspace' },
  { label: 'Categories', icon: FiTag, path: '/portfolio-categories' },
  { label: 'Transactions', icon: FiFileText, path: '/transactions' },
];

const strategyItems = [
  { label: 'Strategy Manager', icon: FaBrain, path: '/strategies-manager' },
  { label: 'Strategies', icon: FiTarget, path: '/strategies' },
];

const settingsItems = [
  { label: 'Settings', icon: FiSettings, path: '/settings' },
];

interface NavItemProps {
  icon: React.ElementType;
  label: string;
  path: string;
  isActive: boolean;
  onClick: () => void;
  badge?: number;
  showLabel?: boolean;
}

const NavItem: React.FC<NavItemProps> = ({ icon: Icon, label, path, isActive, onClick, badge, showLabel = true }) => {
  const hoverBg = 'bg.muted';
  const activeBg = 'bg.subtle';
  const activeColor = 'fg.default';
  const color = 'fg.muted';
  const hoverColor = 'fg.default';

  return (
    <Flex
      align="center"
      px={4}
      py={3}
      cursor="pointer"
      role="group"
      fontWeight="semibold"
      transition="all 0.2s"
      borderRadius="lg"
      justifyContent={showLabel ? 'flex-start' : 'center'}
      bg={isActive ? activeBg : 'transparent'}
      color={isActive ? activeColor : color}
      _hover={{
        bg: isActive ? activeBg : hoverBg,
        color: isActive ? activeColor : hoverColor,
      }}
      onClick={onClick}
      position="relative"
      data-nav-path={path}
      data-active={isActive ? 'true' : 'false'}
    >
      <Icon size={18} />
      {showLabel && (
        <Text ml={3} fontSize="sm">
          {label}
        </Text>
      )}
      {badge && badge > 0 && (
        <Badge
          ml="auto"
          size="sm"
          colorScheme="red"
          variant="solid"
          borderRadius="full"
          minW={5}
          h={5}
          display="flex"
          alignItems="center"
          justifyContent="center"
          fontSize="xs"
        >
          {badge > 99 ? '99+' : badge}
        </Badge>
      )}
    </Flex>
  );
};

const DashboardLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const sidebarBg = 'bg.sidebar';
  const headerBg = 'bg.header';
  const borderColor = 'border.subtle';
  const appBg = 'bg.canvas';
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
  const [isDesktop] = useMediaQuery(['(min-width: 48em)']);
  const [totals, setTotals] = useState<{ value: number; dayPnL: number; positions: number }>({ value: 0, dayPnL: 0, positions: 0 });
  const [headerStats, setHeaderStats] = useState<{ label: string; sublabel: string }>({ label: 'Combined Portfolio', sublabel: '' });

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_OPEN_STORAGE_KEY, isSidebarOpen ? '1' : '0');
    } catch {
      // ignore storage errors
    }
  }, [isSidebarOpen]);

  // Remember last successful route so we can restore after login/session refresh.
  useEffect(() => {
    try {
      const fullPath = `${location.pathname}${location.search || ''}${location.hash || ''}`;
      window.localStorage.setItem(LAST_ROUTE_STORAGE_KEY, fullPath);
    } catch {
      // ignore storage errors
    }
  }, [location.hash, location.pathname, location.search]);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await portfolioApi.getLive();
        const data = (res as any)?.data || res;
        const accounts = Object.values<any>(data?.accounts || {});
        const value = accounts.reduce((sum, a: any) => sum + (a.account_summary?.net_liquidation || 0), 0);
        const dayPnL = accounts.reduce((sum, a: any) => sum + (a.account_summary?.day_change || 0), 0);
        const positions = accounts.reduce((sum, a: any) => sum + ((a.all_positions || []).length || 0), 0);
        setTotals({ value, dayPnL, positions });
        setHeaderStats({
          label: 'Combined Portfolio',
          sublabel: `${formatCurrency(value)} • ${formatSignedCurrency(dayPnL)}`,
        });
      } catch (e) {
        // leave defaults
      }
    };
    load();
  }, []);

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(amount || 0);
  const formatSignedCurrency = (amount: number) => {
    const f = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Math.abs(amount || 0));
    return `${(amount || 0) >= 0 ? '+' : '-'}${f}`;
  };

  const sidebarWidth = isSidebarOpen ? 64 : 16;

  const marketOnly = appSettingsReady ? Boolean(appSettings?.market_only_mode) : true;
  const isAdmin = user?.role === 'admin';
  const portfolioEnabled = isAdmin || (!marketOnly && Boolean(appSettings?.portfolio_enabled));
  const strategyEnabled = isAdmin || (!marketOnly && Boolean(appSettings?.strategy_enabled));

  const isPathActive = React.useCallback((itemPath: string) => {
    const currentPath = location.pathname || '/';
    if (itemPath === '/') {
      return currentPath === '/' || currentPath === '/market/dashboard';
    }
    return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
  }, [location.pathname]);

  const renderSection = (title: string, items: typeof marketItems, showLabel: boolean) => (
    <Box>
      {showLabel ? (
        <Text fontSize="xs" color="fg.muted" px={3} mb={1} mt={3}>
          {title}
        </Text>
      ) : null}
      <VStack gap={1} align="stretch">
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
      </VStack>
    </Box>
  );

  const renderNav = (opts: { showLabel: boolean; px: any }) => (
    <VStack gap={2} px={opts.px} py={4} align="stretch">
      {renderSection('MARKET', marketItems, opts.showLabel)}
      {portfolioEnabled ? renderSection('PORTFOLIO', portfolioItems, opts.showLabel) : null}
      {strategyEnabled ? renderSection('STRATEGY', strategyItems, opts.showLabel) : null}
      {isAdmin ? renderSection('SETTINGS', settingsItems, opts.showLabel) : null}
    </VStack>
  );

  return (
    <Flex h="100vh" w="100vw" bg={appBg} overflow="hidden">
      {/* Desktop rail */}
      {isDesktop ? (
        <Box
          w={sidebarWidth}
          flexShrink={0}
          bg={sidebarBg}
          borderRight="1px"
          borderColor={borderColor}
          h="100vh"
          overflowY="auto"
          transition="width 0.2s ease"
        >
          <VStack gap={0} align="stretch">
            {/* Logo/Brand */}
            <Flex align="center" px={isSidebarOpen ? 6 : 3} py={4} borderBottom="1px" borderColor={borderColor}>
              <Box
                w={8}
                h={8}
                bg="brand.500"
                borderRadius="lg"
                display="flex"
                alignItems="center"
                justifyContent="center"
                mr={isSidebarOpen ? 3 : 0}
              >
                <Text color="white" fontWeight="bold" fontSize="sm">
                  A
                </Text>
              </Box>
              {isSidebarOpen ? (
                <Text fontSize="lg" fontWeight="bold" color="brand.500">
                  AxiomFolio
                </Text>
              ) : null}
            </Flex>

            {isSidebarOpen ? <AppDivider /> : null}

            {/* Navigation */}
            {renderNav({ showLabel: isSidebarOpen, px: isSidebarOpen ? 4 : 2 })}

            {/* Quick Stats */}
            {isSidebarOpen && (
              <Box px={4} py={4} mt="auto">
                <VStack gap={2} align="stretch">
                  <HStack justify="space-between">
                    <Text fontSize="xs" fontWeight="semibold" color="fg.subtle">
                      {headerStats.label}
                    </Text>
                    <Text fontSize="xs" fontWeight="semibold" color="fg.muted">
                      {headerStats.sublabel || formatSignedCurrency(totals.dayPnL)}
                    </Text>
                  </HStack>
                  <AppDivider />
                  <Text fontSize="xs" fontWeight="semibold" color="fg.subtle" textTransform="uppercase">
                    Quick Stats
                  </Text>
                  <HStack justify="space-between">
                    <Text fontSize="xs" color="fg.subtle">Day P&L</Text>
                    <Text fontSize="xs" fontWeight="semibold" color={totals.dayPnL >= 0 ? 'green.400' : 'red.400'}>
                      {formatSignedCurrency(totals.dayPnL)}
                    </Text>
                  </HStack>
                  <HStack justify="space-between">
                    <Text fontSize="xs" color="fg.subtle">Positions</Text>
                    <Text fontSize="xs" fontWeight="semibold">
                      {totals.positions}
                    </Text>
                  </HStack>
                  <HStack justify="space-between">
                    <Text fontSize="xs" color="fg.subtle">Margin Used</Text>
                    <Text fontSize="xs" fontWeight="semibold" color="orange.400">
                      23%
                    </Text>
                  </HStack>
                </VStack>
              </Box>
            )}
          </VStack>
        </Box>
      ) : null}

      {/* Mobile overlay nav */}
      {!isDesktop ? (
        <DialogRoot open={isMobileNavOpen} onOpenChange={(d) => setIsMobileNavOpen(Boolean(d.open))}>
          <DialogBackdrop />
          <DialogPositioner inset={0} justifyContent="flex-start" alignItems="stretch" p={0} m={0}>
            <DialogContent
              position="fixed"
              top={0}
              left={0}
              w="280px"
              maxW="80vw"
              h="100vh"
              borderRadius={0}
              bg={sidebarBg}
              borderRight="1px"
              borderColor={borderColor}
              m={0}
            >
              <VStack gap={0} align="stretch" h="full">
                <Flex align="center" px={6} py={4} borderBottom="1px" borderColor={borderColor}>
                  <Box w={8} h={8} bg="brand.500" borderRadius="lg" display="flex" alignItems="center" justifyContent="center" mr={3}>
                    <Text color="white" fontWeight="bold" fontSize="sm">
                      A
                    </Text>
                  </Box>
                  <Text fontSize="lg" fontWeight="bold" color="brand.500">
                    AxiomFolio
                  </Text>
                </Flex>
                <AppDivider />
                <Box flex={1} overflowY="auto">
                  {renderNav({ showLabel: true, px: 4 })}
                </Box>
              </VStack>
            </DialogContent>
          </DialogPositioner>
        </DialogRoot>
      ) : null}

      {/* Main Content */}
      <Box flex={1} minW={0} overflowX="hidden">
        {/* Header */}
        <Flex
          h={16}
          alignItems="center"
          justifyContent="space-between"
          px={6}
          bg={headerBg}
          borderBottom="1px"
          borderColor={borderColor}
        >
          <HStack gap={4}>
            <IconButton
              size="md"
              variant="ghost"
              aria-label="Menu"
              position="relative"
              zIndex={2}
              color="fg.default"
              onClick={() => {
                if (isDesktop) {
                  setIsSidebarOpen((v) => !v);
                } else {
                  setIsMobileNavOpen(true);
                }
              }}
            >
              <FiMenu />
            </IconButton>
            {/* Global Account Selection */}
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={accountsLoading}
              style={{
                width: 260,
                fontSize: 12,
                padding: '6px 8px',
                borderRadius: 8,
                border: '1px solid var(--chakra-colors-border-subtle)',
                background: 'var(--chakra-colors-bg-input)',
                color: 'var(--chakra-colors-fg-default)',
              }}
            >
              <option value="all">All Accounts</option>
              <option value="taxable">Taxable</option>
              <option value="ira">Tax-Deferred (IRA)</option>
              {accounts.map((a) => (
                <option key={a.account_number} value={a.account_number}>
                  {a.account_name || a.account_number}
                </option>
              ))}
            </select>
            {/* REMOVED: Redundant page name display */}
          </HStack>

          <HStack gap={4}>
            <IconButton size="md" variant="ghost" aria-label="Notifications" position="relative" color="fg.default">
              <FiBell />
              <Badge
                position="absolute"
                top="6px"
                right="6px"
                borderRadius="full"
                bg="red.500"
                w={2}
                h={2}
              />
            </IconButton>
            <MenuRoot>
              <MenuTrigger asChild>
                <Button size="sm" variant="ghost">
                  <HStack gap={2}>
                    <Box w={8} h={8} borderRadius="full" bg="brand.500" display="flex" alignItems="center" justifyContent="center">
                      <Text fontSize="xs" fontWeight="bold" color="white">
                        {(user?.username || 'U').slice(0, 1).toUpperCase()}
                      </Text>
                    </Box>
                    <Text fontSize="sm">{user?.username || 'Account'}</Text>
                  </HStack>
                </Button>
              </MenuTrigger>
              <MenuContent>
                <MenuItem value="settings" onClick={() => navigate('/settings')}>Account Settings</MenuItem>
                {portfolioEnabled ? <MenuItem value="portfolio" onClick={() => navigate('/portfolio')}>Portfolio</MenuItem> : null}
                {portfolioEnabled ? <MenuItem value="workspace" onClick={() => navigate('/workspace')}>Workspace</MenuItem> : null}
                <MenuItem value="logout" onClick={() => { logout(); navigate('/login'); }}>Logout</MenuItem>
              </MenuContent>
            </MenuRoot>
          </HStack>
        </Flex>

        {/* Page Content */}
        <Box p={4} h="calc(100vh - 4rem)" overflowY="auto" overflowX="hidden" minW={0}>
          <Outlet />
        </Box>
      </Box>
    </Flex>
  );
};

export default DashboardLayout; 