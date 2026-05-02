import type { ReactElement } from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminLayoutClient } from "../admin-layout-client";
import { BrainContextProvider } from "@/lib/brain-context";
import { buildNavGroups } from "@/lib/admin-navigation";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    refresh: vi.fn(),
  }),
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

describe("AdminLayoutClient (WS-82 nav reorder — Brain, SYSTEMS, Money demoted)", () => {
  it("sidebar link count matches buildNavGroups; Brain/SYSTEMS/Money headings; hides Tasks/Calendar/Trust", () => {
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
    expect(homeLinks).toHaveLength(1);
    homeLinks.forEach((el) => {
      expect(el.getAttribute("href")).toBe("/admin");
      expect(within(el as HTMLElement).getByText("Studio")).toBeTruthy();
    });
    expect(screen.getAllByText("Money", { exact: true }).some((el) => el.tagName === "P")).toBe(
      true,
    );
    expect(screen.getAllByText("Brain", { exact: true }).some((el) => el.tagName === "P")).toBe(
      true,
    );
    expect(
      screen.getAllByText("SYSTEMS", { exact: true }).some((el) => el.tagName === "P"),
    ).toBe(true);

    expect(
      within(nav).queryByRole("link", { name: /Tasks \(company\)/i }),
    ).toBeNull();
    expect(within(nav).queryByRole("link", { name: /^Calendar$/i })).toBeNull();
    expect(within(nav).queryByRole("link", { name: /^Circles$/ })).toBeNull();
    expect(within(nav).queryByRole("link", { name: /Delegated access/i })).toBeNull();

    expect(
      within(nav).getByRole("link", { name: /^Architecture$/ }).getAttribute("href"),
    ).toBe("/admin/architecture");
    expect(within(nav).getByRole("link", { name: /^Docs$/ }).getAttribute("href")).toBe(
      "/admin/docs",
    );
    expect(
      within(nav).getByRole("link", { name: /^Goals$/ }).getAttribute("href"),
    ).toBe("/admin/goals");
    expect(
      within(nav).getByRole("link", { name: /^Products$/ }).getAttribute("href"),
    ).toBe("/admin/products");

    expect(
      within(nav).getByRole("link", { name: /^People$/ }).getAttribute("href"),
    ).toBe("/admin/people");

    expect(within(nav).queryByText("Trackers", { exact: true })).toBeNull();
    expect(within(nav).queryByText("Trust", { exact: true })).toBeNull();

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
    expect(within(nav).getByRole("link", { name: /^Epics$/ }).getAttribute("href")).toBe(
      "/admin/workstreams",
    );
    expect(within(nav).queryByRole("link", { name: /^Sprints$/ })).toBeNull();
    expect(within(nav).queryByRole("link", { name: /^PR pipeline$/i })).toBeNull();
    expect(
      within(nav).queryByRole("link", { name: /Founder actions/i }),
    ).toBeNull();

    const convoLink = within(nav).getByRole("link", { name: /Conversations/i });
    expect(convoLink.getAttribute("href")).toBe("/admin/conversations");
    expect(within(convoLink).getByText("4 pending")).toBeTruthy();

    const footer = screen.getByTestId("admin-vendor-footer");
    const vendorAnchors = within(footer).getAllByRole("link");
    expect(vendorAnchors).toHaveLength(7);

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

describe("AdminLayoutClient mobile drawer", () => {
  it("renders hamburger control with lg:hidden", () => {
    renderAdminLayout(
      <AdminLayoutClient founderPending={null} expensesPending={null}>
        <span />
      </AdminLayoutClient>,
    );
    const btn = screen.getByRole("button", { name: /open navigation menu/i });
    expect(btn.className).toContain("lg:hidden");
  });

  it("toggles drawer when hamburger is clicked repeatedly", async () => {
    const user = userEvent.setup();
    renderAdminLayout(
      <AdminLayoutClient founderPending={null} expensesPending={null}>
        <span />
      </AdminLayoutClient>,
    );
    const menuBtn = screen.getByRole("button", { name: /open navigation menu/i });
    await user.click(menuBtn);
    expect(screen.getByTestId("admin-mobile-drawer")).toBeTruthy();
    await user.click(menuBtn);
    expect(screen.queryByTestId("admin-mobile-drawer")).toBeNull();
  });

  it("opens drawer when hamburger is clicked", async () => {
    const user = userEvent.setup();
    renderAdminLayout(
      <AdminLayoutClient founderPending={null} expensesPending={null}>
        <span />
      </AdminLayoutClient>,
    );
    expect(screen.queryByTestId("admin-mobile-drawer")).toBeNull();
    await user.click(screen.getByRole("button", { name: /open navigation menu/i }));
    expect(screen.getByTestId("admin-mobile-drawer")).toBeTruthy();
    expect(screen.getByTestId("admin-mobile-drawer-backdrop")).toBeTruthy();
  });

  it("closes drawer when backdrop is clicked", async () => {
    const user = userEvent.setup();
    renderAdminLayout(
      <AdminLayoutClient founderPending={null} expensesPending={null}>
        <span />
      </AdminLayoutClient>,
    );
    await user.click(screen.getByRole("button", { name: /open navigation menu/i }));
    await user.click(screen.getByRole("button", { name: /close menu/i }));
    expect(screen.queryByTestId("admin-mobile-drawer")).toBeNull();
    expect(screen.queryByTestId("admin-mobile-drawer-backdrop")).toBeNull();
  });
});
