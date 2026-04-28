import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { Meta, StoryObj } from "@storybook/react";

import { MockDashboardLayout } from "./DashboardLayout.mock";

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

const StoryShell: React.FC<{
  initialPath?: string;
  collapsed?: boolean;
  chrome?: "default" | "admin";
}> = ({ initialPath = "/", collapsed = false, chrome = "default" }) => (
  <MemoryRouter initialEntries={[initialPath]}>
    <Routes>
      <Route path="/" element={<MockDashboardLayout collapsed={collapsed} chrome={chrome} />}>
        <Route
          index
          element={storyPlaceholder(
            "DashboardLayout (mock shell)",
            "Visual-only sidebar, header, and outlet for design QA — no AxiomFolio runtime."
          )}
        />
        <Route
          path="market/coverage"
          element={storyPlaceholder(
            "Market / Coverage",
            "Nested route under the mock layout — check sidebar active state."
          )}
        />
        <Route
          path="settings/admin/system"
          element={storyPlaceholder(
            "Admin settings (mock)",
            "Admin chrome variant shows portfolio-style header hints."
          )}
        />
        <Route
          path="*"
          element={storyPlaceholder(
            "DashboardLayout route",
            "Use sidebar links to verify active state and collapse width."
          )}
        />
      </Route>
    </Routes>
  </MemoryRouter>
);

export const Expanded_Default: Story = {
  render: () => <StoryShell initialPath="/" collapsed={false} chrome="default" />,
};

export const Collapsed_Default: Story = {
  render: () => <StoryShell initialPath="/market/coverage" collapsed={true} chrome="default" />,
};

export const Admin_PortfolioEnabled_Expanded: Story = {
  render: () => <StoryShell initialPath="/settings/admin/system" collapsed={false} chrome="admin" />,
};

export const Admin_PortfolioEnabled_Collapsed: Story = {
  render: () => <StoryShell initialPath="/settings/admin/system" collapsed={true} chrome="admin" />,
};
