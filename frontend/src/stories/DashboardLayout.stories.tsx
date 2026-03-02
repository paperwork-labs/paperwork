import React from "react";
import { Box, Text } from "@chakra-ui/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import DashboardLayout from "../components/layout/DashboardLayout";
import { AuthProvider, AuthContext, type AuthContextValue } from "../context/AuthContext";
import { AccountProvider, AccountContext, type AccountContextValue } from "../context/AccountContext";

export default {
  title: "App/Layout/DashboardLayout",
};

const StoryShell: React.FC<{ initialPath?: string; collapsed?: boolean }> = ({
  initialPath = "/",
  collapsed = false,
}) => {
  React.useEffect(() => {
    try {
      // Keep stories deterministic and unauthenticated by default.
      localStorage.removeItem("qm_token");
      localStorage.setItem("qm.ui.sidebar_open", collapsed ? "0" : "1");
    } catch {
      // ignore storage errors in sandboxed environments
    }
  }, [collapsed]);

  return (
    <AuthProvider>
      <AccountProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/" element={<DashboardLayout />}>
              <Route
                index
                element={
                  <Box p={4}>
                    <Text fontSize="lg" fontWeight="semibold">
                      DashboardLayout Story
                    </Text>
                    <Text fontSize="sm" color="fg.muted" mt={1}>
                      This is a visual shell to validate sidebar/header behavior in Ladle.
                    </Text>
                  </Box>
                }
              />
              <Route
                path="*"
                element={
                  <Box p={4}>
                    <Text fontSize="lg" fontWeight="semibold">
                      DashboardLayout Story Route
                    </Text>
                    <Text fontSize="sm" color="fg.muted" mt={1}>
                      Use sidebar links to verify active state and menu positioning.
                    </Text>
                  </Box>
                }
              />
            </Route>
          </Routes>
        </MemoryRouter>
      </AccountProvider>
    </AuthProvider>
  );
};

export const Expanded_Default = () => <StoryShell initialPath="/" collapsed={false} />;

export const Collapsed_Default = () => <StoryShell initialPath="/market/coverage" collapsed={true} />;

const MockedProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const authMock = React.useMemo<AuthContextValue>(
    () => ({
      user: {
        id: 1,
        username: "admin",
        email: "admin@example.com",
        is_active: true,
        role: "admin",
      },
      token: "storybook-token",
      ready: true,
      appSettings: {
        market_only_mode: false,
        portfolio_enabled: true,
        strategy_enabled: true,
      },
      appSettingsReady: true,
      login: async () => {},
      register: async () => {},
      logout: () => {},
      refreshMe: async () => {},
      refreshAppSettings: async () => {},
    }),
    []
  );

  const [selected, setSelected] = React.useState<string>("all");
  const accountMock = React.useMemo<AccountContextValue>(
    () => ({
      accounts: [
        { id: 1, account_number: "IBKR_MAIN", account_name: "IBKR (FlexQuery)" },
        { id: 2, account_number: "SCHWAB", account_name: "SCHWAB" },
      ],
      loading: false,
      error: null,
      selected,
      setSelected,
      refetch: () => {},
    }),
    [selected]
  );

  return (
    <AuthContext.Provider value={authMock}>
      <AccountContext.Provider value={accountMock}>{children}</AccountContext.Provider>
    </AuthContext.Provider>
  );
};

const MockedStoryShell: React.FC<{ initialPath?: string; collapsed?: boolean }> = ({
  initialPath = "/settings/admin/dashboard",
  collapsed = false,
}) => {
  React.useEffect(() => {
    try {
      localStorage.setItem("qm.ui.sidebar_open", collapsed ? "0" : "1");
    } catch {
      // ignore storage errors in sandboxed environments
    }
  }, [collapsed]);

  return (
    <MockedProviders>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={<DashboardLayout />}>
            <Route
              index
              element={
                <Box p={4}>
                  <Text fontSize="lg" fontWeight="semibold">
                    DashboardLayout Story (Mocked Admin)
                  </Text>
                  <Text fontSize="sm" color="fg.muted" mt={1}>
                    Admin + portfolio-enabled mock state to preview gated footer and admin actions.
                  </Text>
                </Box>
              }
            />
            <Route
              path="*"
              element={
                <Box p={4}>
                  <Text fontSize="lg" fontWeight="semibold">
                    DashboardLayout Story Route
                  </Text>
                  <Text fontSize="sm" color="fg.muted" mt={1}>
                    Use links/menus to validate admin header + sidebar behavior.
                  </Text>
                </Box>
              }
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </MockedProviders>
  );
};

export const Admin_PortfolioEnabled_Expanded = () => (
  <MockedStoryShell initialPath="/settings/admin/dashboard" collapsed={false} />
);

export const Admin_PortfolioEnabled_Collapsed = () => (
  <MockedStoryShell initialPath="/settings/admin/dashboard" collapsed={true} />
);

