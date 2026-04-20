import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { AccountProvider } from './context/AccountContext';
import { AuthProvider } from './context/AuthContext';
import { ColorModeProvider } from './theme/colorMode';
import ErrorBoundary from './components/ErrorBoundary';

import RequireAuth from './components/auth/RequireAuth';
import RequireNonMarketAccess from './components/auth/RequireNonMarketAccess';
import RequireAdmin from './components/auth/RequireAdmin';
import AuthLogoutListener from './components/auth/AuthLogoutListener';
import { AppCommandLayer } from './components/cmdk/AppCommandLayer';
import { InstallPrompt } from './components/pwa/InstallPrompt';

const DashboardLayout = React.lazy(() => import('./components/layout/DashboardLayout'));
const PortfolioOverview = React.lazy(() => import('./pages/portfolio/PortfolioOverview'));
const PortfolioHoldings = React.lazy(() => import('./pages/portfolio/PortfolioHoldings'));
const HoldingDetail = React.lazy(() => import('./pages/HoldingDetail'));
const PortfolioOptions = React.lazy(() => import('./pages/portfolio/PortfolioOptions'));
const PortfolioCategories = React.lazy(() => import('./pages/portfolio/PortfolioCategories'));
const PortfolioTransactions = React.lazy(() => import('./pages/portfolio/PortfolioTransactions'));
const PortfolioTaxCenter = React.lazy(() => import('./pages/portfolio/PortfolioTaxCenter'));
const PortfolioOrders = React.lazy(() => import('./pages/portfolio/PortfolioOrders'));
const Strategies = React.lazy(() => import('./pages/Strategies'));
const StrategiesManager = React.lazy(() => import('./pages/StrategiesManager'));
const StrategyDetail = React.lazy(() => import('./pages/StrategyDetail'));
const SettingsShell = React.lazy(() => import('./pages/SettingsShell'));
const SettingsConnections = React.lazy(() => import('./pages/SettingsConnections'));
const SettingsProfile = React.lazy(() => import('./pages/SettingsProfile'));
const SettingsPreferences = React.lazy(() => import('./pages/SettingsPreferences'));
const SettingsNotifications = React.lazy(() => import('./pages/SettingsNotifications'));
const SettingsMCP = React.lazy(() => import('./pages/SettingsMCP'));
const PortfolioWorkspace = React.lazy(() => import('./pages/PortfolioWorkspace'));
const PortfolioAllocation = React.lazy(() => import('./pages/PortfolioAllocation'));
const PortfolioIncome = React.lazy(() => import('./pages/PortfolioIncome'));
const Login = React.lazy(() => import('./pages/Login'));
const Register = React.lazy(() => import('./pages/Register'));
const Onboarding = React.lazy(() => import('./pages/Onboarding'));
const AuthCallback = React.lazy(() => import('./pages/AuthCallback'));
const SystemStatus = React.lazy(() => import('./pages/SystemStatus'));
const MarketDashboard = React.lazy(() => import('./pages/MarketDashboard'));
const MarketTracked = React.lazy(() => import('./pages/MarketTracked'));
const MarketEducation = React.lazy(() => import('./pages/MarketEducation'));
const MarketIntelligence = React.lazy(() => import('./pages/MarketIntelligence'));
const Invite = React.lazy(() => import('./pages/Invite'));
const WhyFree = React.lazy(() => import('./pages/WhyFree'));
const Pricing = React.lazy(() => import('./pages/Pricing'));
const SettingsUsers = React.lazy(() => import('./pages/SettingsUsers'));
const AdminAgent = React.lazy(() => import('./pages/AdminAgent'));
const Terminal = React.lazy(() => import('./pages/Terminal'));
const Scanner = React.lazy(() => import('./pages/Scanner'));
const Picks = React.lazy(() => import('./pages/Picks'));
const PicksValidator = React.lazy(() => import('./pages/admin/PicksValidator'));
const WalkForward = React.lazy(() => import('./pages/Backtest/WalkForward'));
const BacktestMonteCarlo = React.lazy(() => import('./pages/Backtest/MonteCarlo'));
const ConnectAccounts = React.lazy(() => import('./pages/ConnectAccounts'));
const AccountsManagement = React.lazy(() => import('./pages/AccountsManagement'));
const PortfolioImport = React.lazy(() => import('./pages/PortfolioImport'));

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

function LegacyStrategyDetailRedirect() {
  const { strategyId } = useParams<{ strategyId: string }>();
  if (!strategyId) {
    return <Navigate to="/market/strategies" replace />;
  }
  return <Navigate to={`/market/strategies/${strategyId}`} replace />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ColorModeProvider>
        <AuthProvider>
          <AccountProvider>
            <ErrorBoundary>
              <Router>
                <AuthLogoutListener />
                <AppCommandLayer />
                <Suspense fallback={<RouteFallback />}>
                  <Routes>
                      <Route path="/onboarding" element={<RequireAuth><Onboarding /></RequireAuth>} />
                      <Route path="/" element={<RequireAuth><DashboardLayout /></RequireAuth>}>
                        {/* Market */}
                        <Route index element={<MarketDashboard />} />
                        <Route path="market/dashboard" element={<MarketDashboard />} />
                        <Route path="market/tracked" element={<MarketTracked />} />
                        <Route path="market/education" element={<MarketEducation />} />
                        <Route path="market/intelligence" element={<MarketIntelligence />} />
                        <Route path="market/scanner" element={<Scanner />} />
                        <Route path="picks" element={<Picks />} />
                        <Route
                          path="admin/picks"
                          element={
                            <RequireAdmin>
                              <PicksValidator />
                            </RequireAdmin>
                          }
                        />
                        <Route path="terminal" element={<Terminal />} />
                        <Route path="backtest/walk-forward" element={<WalkForward />} />

                        {/* Legacy strategy URLs → /market/strategies* */}
                        <Route path="strategies" element={<Navigate to="/market/strategies" replace />} />
                        <Route path="strategies/:strategyId" element={<LegacyStrategyDetailRedirect />} />
                        <Route
                          path="strategies-manager"
                          element={<Navigate to="/market/strategies/manage" replace />}
                        />

                        {/* Portfolio section */}
                        <Route element={<RequireNonMarketAccess section="portfolio" />}>
                          <Route path="portfolio" element={<PortfolioOverview />} />
                          <Route path="portfolio/holdings" element={<PortfolioHoldings />} />
                          <Route path="holding/:symbol" element={<HoldingDetail />} />
                          <Route path="portfolio/options" element={<PortfolioOptions />} />
                          <Route path="portfolio/transactions" element={<PortfolioTransactions />} />
                          <Route path="portfolio/categories" element={<PortfolioCategories />} />
                          <Route path="portfolio/tax" element={<PortfolioTaxCenter />} />
                          <Route path="portfolio/orders" element={<PortfolioOrders />} />
                          <Route path="portfolio/workspace" element={<PortfolioWorkspace />} />
                          <Route path="portfolio/allocation" element={<PortfolioAllocation />} />
                          <Route path="portfolio/income" element={<PortfolioIncome />} />
                          <Route path="portfolio/import" element={<PortfolioImport />} />
                          {/* Connect hub (3h): unified broker connection UX. Routes
                              live under the same access gate as other portfolio
                              pages because the underlying API requires it. */}
                          <Route path="connect" element={<ConnectAccounts />} />
                          <Route path="accounts/manage" element={<AccountsManagement />} />
                        </Route>

                        {/* Strategy (under Market in nav, same access as market) */}
                        <Route path="market/strategies" element={<Strategies />} />
                        <Route path="market/strategies/manage" element={<StrategiesManager />} />
                        <Route path="market/strategies/:strategyId" element={<StrategyDetail />} />

                        {/* Backtest analysis (Pro+ research kit) */}
                        <Route path="backtest/monte-carlo" element={<BacktestMonteCarlo />} />

                        {/* Legacy /admin/agent → canonical /settings/admin/agent */}
                        <Route
                          path="admin/agent"
                          element={<Navigate to="/settings/admin/agent" replace />}
                        />
                        <Route
                          path="admin/agent/capabilities"
                          element={<Navigate to="/settings/admin/agent" replace />}
                        />

                        {/* Settings */}
                        <Route path="settings" element={<SettingsShell />}>
                          <Route index element={<Navigate to="profile" replace />} />
                          <Route path="profile" element={<SettingsProfile />} />
                          <Route path="preferences" element={<SettingsPreferences />} />
                          <Route path="notifications" element={<SettingsNotifications />} />
                          <Route path="connections" element={<SettingsConnections />} />
                          <Route path="mcp" element={<SettingsMCP />} />
                          <Route element={<RequireAdmin />}>
                            <Route path="admin/system" element={<SystemStatus />} />
                            <Route path="admin/users" element={<SettingsUsers />} />
                            <Route path="admin/agent" element={<AdminAgent />} />
                            <Route
                              path="admin/agent/capabilities"
                              element={<Navigate to="/settings/admin/agent" replace />}
                            />
                          </Route>
                        </Route>
                      </Route>
                      <Route path="/login" element={<Login />} />
                      <Route path="/register" element={<Register />} />
                      <Route path="/why-free" element={<WhyFree />} />
                      <Route path="/pricing" element={<Pricing />} />
                      <Route path="/auth/callback" element={<AuthCallback />} />
                      <Route path="/invite/:token" element={<Invite />} />
                    </Routes>
                  </Suspense>
                  <Toaster
                    position="top-right"
                    toastOptions={{
                      style: {
                        background: 'rgb(var(--bg-panel) / 1)',
                        color: 'var(--foreground)',
                        border: '1px solid var(--border)',
                      },
                    }}
                  />
                  <InstallPrompt />
                </Router>
              </ErrorBoundary>
            </AccountProvider>
          </AuthProvider>
      </ColorModeProvider>
    </QueryClientProvider>
  );
}

export default App;
