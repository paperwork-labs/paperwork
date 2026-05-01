import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StatCard } from "../stat-card";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

afterEach(() => {
  cleanup();
});

describe("StatCard", () => {
  it("renders label and value", () => {
    render(<StatCard label="Open PRs" value={42} />);
    expect(screen.getByText("Open PRs")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
  });

  it("with href: renders as a link", () => {
    render(<StatCard label="Products" value="Catalog" href="/admin/products" />);
    const link = screen.getByRole("link", { name: /products/i });
    expect(link.tagName.toLowerCase()).toBe("a");
    expect(link.getAttribute("href")).toBe("/admin/products");
  });

  it("without href: renders as a div", () => {
    render(<StatCard label="CI" value="3/5" />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("CI").closest("div")).toBeTruthy();
  });

  it("trend up shows up arrow and emerald color class", () => {
    render(<StatCard label="Shipped" value={10} delta={{ value: "+2", trend: "up" }} />);
    const deltaRow = screen.getByText(/^↑\s+\+2$/);
    expect(deltaRow.className.includes("text-emerald-400")).toBe(true);
  });
});
