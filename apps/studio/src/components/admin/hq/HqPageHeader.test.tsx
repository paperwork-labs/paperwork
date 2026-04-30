import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HqPageHeader } from "./HqPageHeader";

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

describe("HqPageHeader", () => {
  it("renders title and subtitle", () => {
    render(<HqPageHeader title="Workstreams" subtitle="Cross-cutting logs." />);
    expect(screen.getByRole("heading", { level: 1, name: "Workstreams" })).toBeTruthy();
    expect(screen.getByText("Cross-cutting logs.")).toBeTruthy();
  });

  it("renders breadcrumbs", () => {
    render(
      <HqPageHeader
        title="Page"
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Here" },
        ]}
      />,
    );
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Admin" }).getAttribute("href")).toBe("/admin");
  });
});
