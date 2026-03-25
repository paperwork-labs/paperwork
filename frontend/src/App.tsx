import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { AccountProvider } from './context/AccountContext';
import { AuthProvider } from './context/AuthContext';
import { ColorModeProvider } from './theme/colorMode';
import { system } from './theme/system';
import ErrorBoundary from './components/ErrorBoundary';

import RequireAuth from './components/auth/RequireAuth';
import RequireNonMarketAccess from './components/auth/RequireNonMarketAccess';
import RequireAdmin from './components/auth/RequireAdmin';

const DashboardLayout = React.lazy(() => import('./components/layout/DashboardLayout'));
const PortfolioOverview = React.lazy(() => import('./pages/portfolio/PortfolioOverview'));
const PortfolioHoldings = React.lazy(() => import('./pages/portfolio/PortfolioHoldings'));
const PortfolioOptions = React.lazy(() => import('./pages/portfolio/PortfolioOptions'));
const PortfolioCategories = React.lazy(() => import('./pages/portfolio/PortfolioCategories'));
const PortfolioTransactions = React.lazy(() => import('./pages/portfolio/PortfolioTransactions'));
const PortfolioTaxCenter = React.lazy(() => import('./pages/portfolio/PortfolioTaxCenter'));
const PortfolioOrders = React.lazy(() => import('./pages/portfolio/PortfolioOrders'));
const Strategies = React.lazy(() => import('./pages/Strategies'));
const StrategyDetail = React.lazy(() => import('./pages/StrategyDetail'));
const SettingsShell = React.lazy(() => import('./pages/SettingsShell'));
const SettingsConnections = React.lazy(() => import('./pages/SettingsConnections'));
const SettingsProfile = React.lazy(() => import('./pages/SettingsProfile'));
const SettingsPreferences = React.lazy(() => import('./pages/SettingsPreferences'));
const SettingsNotifications = React.lazy(() => import('./pages/SettingsNotifications'));
const PortfolioWorkspace = React.lazy(() => import('./pages/PortfolioWorkspace'));
const Login = React.lazy(() => import('./pages/Login'));
const Register = React.lazy(() => import('./pages/Register'));
const AuthCallback = React.lazy(() => import('./pages/AuthCallback'));
const SystemStatus = React.lazy(() => import('./pages/SystemStatus'));
const MarketDashboard = React.lazy(() => import('./pages/MarketDashboard'));
const MarketTracked = React.lazy(() => import('./pages/MarketTracked'));
const MarketEducation = React.lazy(() => import('./pages/MarketEducation'));
const MarketIntelligence = React.lazy(() => import('./pages/MarketIntelligence'));
const Invite = React.lazy(() => import('./pages/Invite'));
const SettingsUsers = React.lazy(() => import('./pages/SettingsUsers'));
const AdminAgent = React.lazy(() => import('./pages/AdminAgent'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 60 * 5,
    },
  },
});

const RouteFallback: React.FC = () => (
  <div style={{ padding: 16, fontFamily: 'system-ui' }}>Loading…</div>
);

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ColorModeProvider>
        <ChakraProvider value={system}>
          <AuthProvider>
            <AccountProvider>
              <ErrorBoundary>
                <Router>
                  <Suspense fallback={<RouteFallback />}>
                    <Routes>
                      <Route path="/" element={<RequireAuth><DashboardLayout /></RequireAuth>}>
                        {/* Market */}
                        <Route index element={<MarketDashboard />} />
                        <Route path="market/dashboard" element={<MarketDashboard />} />
                        <Route path="market/tracked" element={<MarketTracked />} />
                        <Route path="market/education" element={<MarketEducation />} />
                        <Route path="market/intelligence" element={<MarketIntelligence />} />

                        {/* Portfolio section */}
                        <Route element={<RequireNonMarketAccess section="portfolio" />}>
                          <Route path="portfolio" element={<PortfolioOverview />} />
                          <Route path="portfolio/holdings" element={<PortfolioHoldings />} />
                          <Route path="portfolio/options" element={<PortfolioOptions />} />
                          <Route path="portfolio/transactions" element={<PortfolioTransactions />} />
                          <Route path="portfolio/categories" element={<PortfolioCategories />} />
                          <Route path="portfolio/tax" element={<PortfolioTaxCenter />} />
                          <Route path="portfolio/orders" element={<PortfolioOrders />} />
                          <Route path="portfolio/workspace" element={<PortfolioWorkspace />} />
                        </Route>

                        {/* Strategy section */}
                        <Route element={<RequireNonMarketAccess section="strategy" />}>
                          <Route path="strategies" element={<Strategies />} />
                          <Route path="strategies/:strategyId" element={<StrategyDetail />} />
                          <Route path="strategies-manager" element={<Navigate to="/strategies" replace />} />
                        </Route>

                        {/* Settings */}
                        <Route path="settings" element={<SettingsShell />}>
                          <Route index element={<Navigate to="profile" replace />} />
                          <Route path="profile" element={<SettingsProfile />} />
                          <Route path="preferences" element={<SettingsPreferences />} />
                          <Route path="notifications" element={<SettingsNotifications />} />
                          <Route path="connections" element={<SettingsConnections />} />
                          <Route element={<RequireAdmin />}>
                            <Route path="admin/system" element={<SystemStatus />} />
                            <Route path="admin/users" element={<SettingsUsers />} />
                            <Route path="admin/agent" element={<AdminAgent />} />
                          </Route>
                        </Route>
                      </Route>
                      <Route path="/login" element={<Login />} />
                      <Route path="/register" element={<Register />} />
                      <Route path="/auth/callback" element={<AuthCallback />} />
                      <Route path="/invite/:token" element={<Invite />} />
                    </Routes>
                  </Suspense>
                  <Toaster
                    position="top-right"
                    toastOptions={{
                      style: {
                        background: 'var(--chakra-colors-bg-panel)',
                        color: 'var(--chakra-colors-fg-default)',
                        border: '1px solid var(--chakra-colors-border-subtle)',
                      },
                    }}
                  />
                </Router>
              </ErrorBoundary>
            </AccountProvider>
          </AuthProvider>
        </ChakraProvider>
      </ColorModeProvider>
    </QueryClientProvider>
  );
}

export default App;
