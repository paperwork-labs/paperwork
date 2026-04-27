import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import DashboardLayout from "@axiomfolio/components/layout/DashboardLayout";
import { AuthProvider, AuthContext, type AuthContextValue } from "@axiomfolio/context/AuthContext";
import { AccountProvider, AccountContext, type AccountContextValue } from "@axiomfolio/context/AccountContext";
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: "App/Layout/DashboardLayout",
};
export default meta;

type Story = StoryObj;

const storyPlaceholder = (title: string, subtitle: string) => (
  <div className="p-4">
    <div className="text-lg font-semibold">{title}</div>
    <div className="mt-1 text-sm text-muted-foreground">{subtitle}</div>
  </div>
);

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
                element={storyPlaceholder(
                  "DashboardLayout Story",
                  "This is a visual shell to validate sidebar/header behavior in Storybook."
                )}
              />
              <Route
                path="*"
                element={storyPlaceholder(
                  "DashboardLayout Story Route",
                  "Use sidebar links to verify active state and menu positioning."
                )}
              />
            </Route>
          </Routes>
        </MemoryRouter>
      </AccountProvider>
    </AuthProvider>
  );
};

export const Expanded_Default: Story = {
  render: () => <StoryShell initialPath="/" collapsed={false} />,
};

export const Collapsed_Default: Story = {
  render: () => <StoryShell initialPath="/market/coverage" collapsed={true} />,
};

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
      login: async () => {},
      register: async () => ({ pendingApproval: false }),
      logout: () => {},
      refreshMe: async () => {},
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
  initialPath = "/settings/admin/system",
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
              element={storyPlaceholder(
                "DashboardLayout Story (Mocked Admin)",
                "Admin + portfolio-enabled mock state to preview gated footer and admin actions."
              )}
            />
            <Route
              path="*"
              element={storyPlaceholder(
                "DashboardLayout Story Route",
                "Use links/menus to validate admin header + sidebar behavior."
              )}
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </MockedProviders>
  );
};

export const Admin_PortfolioEnabled_Expanded: Story = {
  render: () => (
  <MockedStoryShell initialPath="/settings/admin/system" collapsed={false} />
),
};

export const Admin_PortfolioEnabled_Collapsed: Story = {
  render: () => (
  <MockedStoryShell initialPath="/settings/admin/system" collapsed={true} />
),
};
