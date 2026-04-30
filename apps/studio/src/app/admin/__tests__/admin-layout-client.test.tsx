import type { ReactElement } from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminLayoutClient } from "../admin-layout-client";
import { BrainContextProvider } from "@/lib/brain-context";
import { buildNavGroups } from "@/lib/admin-navigation";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@clerk/nextjs", () => ({
  UserButton: () => <div data-testid="clerk-user-button-mock" />,
}));

afterEach(() => {
  cleanup();
});

function renderAdminLayout(ui: ReactElement) {
  return render(<BrainContextProvider>{ui}</BrainContextProvider>);
}

describe("AdminLayoutClient (WS-82 PR-IA1 unified Workstreams nav)", () => {
  it("sidebar link count matches buildNavGroups + Money, Trust, Trackers, Calendar", () => {
    renderAdminLayout(
      <AdminLayoutClient
        founderPending={{ count: 4, hasCritical: true }}
        expensesPending={null}
      >
        <p>child</p>
      </AdminLayoutClient>,
    );

    const nav = screen.getAllByRole("navigation", { name: "Admin" })[0]!;
    const navLinks = within(nav).getAllByRole("link");
    const expectedCount = buildNavGroups(
      { count: 4, hasCritical: true },
      null,
    ).reduce((acc, g) => acc + g.items.length, 0);
    expect(navLinks).toHaveLength(expectedCount);

    expect(screen.getAllByText("Paperwork Labs").length).toBeGreaterThan(0);
    const homeLinks = screen.getAllByTestId("admin-sidebar-home-link");
    expect(homeLinks).toHaveLength(2);
    homeLinks.forEach((el) => {
      expect(el.getAttribute("href")).toBe("/admin");
      expect(within(el as HTMLElement).getByText("Studio")).toBeTruthy();
    });
    expect(screen.getAllByText("Money", { exact: true }).some((el) => el.tagName === "P")).toBe(
      true,
    );
    expect(screen.getAllByText("Trust", { exact: true }).some((el) => el.tagName === "P")).toBe(
      true,
    );
    expect(screen.getAllByText("Trackers").some((el) => el.tagName === "P")).toBe(true);
    const archLabels = within(nav).getAllByText("Architecture");
    expect(archLabels.some((el) => el.tagName === "P")).toBe(true);
    expect(
      within(nav).getByRole("link", { name: /^Architecture$/ }).getAttribute("href"),
    ).toBe("/admin/architecture");
    expect(screen.getAllByText("Brain", { exact: true }).length).toBeGreaterThan(0);

    const trackersHeading = within(nav).getByText("Trackers", { exact: true });
    const trackersGroup = trackersHeading.parentElement as HTMLElement;
    expect(
      within(nav).getByRole("link", { name: /^Calendar$/i }).getAttribute("href"),
    ).toBe("/admin/calendar");
    const expensesInNav = within(nav).getByRole("link", {
      name: /Expenses/i,
    });
    expect(expensesInNav.getAttribute("href")).toBe("/admin/expenses");
    expect(
      within(nav).getByRole("link", { name: /^Bills$/ }).getAttribute("href"),
    ).toBe("/admin/bills");
    expect(
      within(nav).getByRole("link", { name: /^Vendors$/ }).getAttribute("href"),
    ).toBe("/admin/vendors");
    expect(
      within(nav).getByRole("link", { name: /^Workstreams$/ }).getAttribute("href"),
    ).toBe("/admin/workstreams");
    expect(within(nav).queryByRole("link", { name: /^Sprints$/ })).toBeNull();
    expect(within(nav).queryByRole("link", { name: /^PR pipeline$/i })).toBeNull();
    expect(
      within(nav).queryByRole("link", { name: /Founder actions/i }),
    ).toBeNull();

    expect(within(nav).getByRole("link", { name: /^Circles$/ }).getAttribute("href")).toBe(
      "/admin/circles",
    );
    expect(
      within(nav).getByRole("link", { name: /Delegated access/i }).getAttribute("href"),
    ).toBe("/admin/delegated");

    const convoLink = within(nav).getByRole("link", { name: /Conversations/i });
    expect(convoLink.getAttribute("href")).toBe("/admin/brain/conversations");
    expect(within(convoLink).getByText("4 pending")).toBeTruthy();

    const footer = screen.getAllByTestId("admin-vendor-footer")[1]!;
    const vendorAnchors = within(footer).getAllByRole("link");
    expect(vendorAnchors).toHaveLength(6);

    expect(within(footer).getByText("Hosting")).toBeTruthy();
    expect(within(footer).getByText("Code")).toBeTruthy();
    expect(within(footer).getByText("AI cost")).toBeTruthy();
  });

  it("shows Expenses live pending badge when expensesPending is provided", () => {
    renderAdminLayout(
      <AdminLayoutClient
        founderPending={{ count: 0, hasCritical: false }}
        expensesPending={{ count: 3, hasCritical: false }}
      >
        <span />
      </AdminLayoutClient>,
    );
    const expenses = screen.getByRole("link", { name: /Expenses/i });
    expect(within(expenses).getByText("3 pending")).toBeTruthy();
  });
});
