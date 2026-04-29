import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminLayoutClient } from "../admin-layout-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin",
}));

vi.mock("@clerk/nextjs", () => ({
  UserButton: () => <div data-testid="clerk-user-button-mock" />,
}));

afterEach(() => {
  cleanup();
});

describe("AdminLayoutClient (WS-69 PR B nav)", () => {
  it("renders 13 sidebar links in 4 sections, Brain bucket, expenses + conversations badge, footer vendors", () => {
    render(
      <AdminLayoutClient
        founderPending={{ count: 4, hasCritical: true }}
      >
        <p>child</p>
      </AdminLayoutClient>,
    );

    const nav = screen.getByRole("navigation", { name: "Admin" });
    const navLinks = within(nav).getAllByRole("link");
    expect(navLinks).toHaveLength(13);

    expect(screen.getByText("Command Center")).toBeTruthy();
    expect(screen.getByText("Trackers")).toBeTruthy();
    const archLabels = within(nav).getAllByText("Architecture");
    expect(archLabels.some((el) => el.tagName === "P")).toBe(true);
    expect(
      within(nav).getByRole("link", { name: /^Architecture$/ }).getAttribute("href"),
    ).toBe("/admin/architecture");
    expect(screen.getByText("Brain")).toBeTruthy();

    const trackersGroup = screen.getByText("Trackers")
      .parentElement as HTMLElement;
    const expensesInTrackers = within(trackersGroup).getByRole("link", {
      name: /Expenses/i,
    });
    expect(expensesInTrackers.getAttribute("href")).toBe("/admin/expenses");
    expect(
      within(trackersGroup).queryByRole("link", { name: /Founder actions/i }),
    ).toBeNull();

    const convoLink = within(nav).getByRole("link", { name: /Conversations/i });
    expect(convoLink.getAttribute("href")).toBe("/admin/brain/conversations");
    expect(within(convoLink).getByText("4 pending")).toBeTruthy();

    const footer = screen.getByTestId("admin-vendor-footer");
    const vendorAnchors = within(footer).getAllByRole("link");
    expect(vendorAnchors).toHaveLength(7);

    expect(within(footer).getByText("Hosting")).toBeTruthy();
    expect(within(footer).getByText("Code")).toBeTruthy();
    expect(within(footer).getByText("AI cost")).toBeTruthy();
    expect(within(footer).getByText("Comms")).toBeTruthy();
  });

  it("shows Expenses static 0 pending badge", () => {
    render(
      <AdminLayoutClient founderPending={{ count: 0, hasCritical: false }}>
        <span />
      </AdminLayoutClient>,
    );
    const expenses = screen.getByRole("link", { name: /Expenses/i });
    expect(within(expenses).getByText("0 pending")).toBeTruthy();
  });
});
