import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HqEmptyState } from "./HqEmptyState";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

afterEach(() => {
  cleanup();
});

describe("HqEmptyState", () => {
  it("renders title and description", () => {
    render(
      <HqEmptyState title="Nothing here" description="Add items to get started." />,
    );
    expect(screen.getByTestId("hq-empty-state")).toBeTruthy();
    expect(screen.getByText("Nothing here")).toBeTruthy();
    expect(screen.getByText("Add items to get started.")).toBeTruthy();
  });

  it("renders href action", () => {
    render(
      <HqEmptyState title="Empty" action={{ label: "Go", href: "/admin" }} />,
    );
    const link = screen.getByRole("link", { name: "Go" });
    expect(link.getAttribute("href")).toBe("/admin");
  });
});
