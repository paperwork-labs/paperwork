import type { ReactNode } from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
import type { FormationDashboardStatus, FormationSummary } from "@/lib/dashboard-formations";
import { FormationCard } from "../components/formation-card";
import { StatusTimeline } from "../components/status-timeline";
import { metadata as dashboardMetadata } from "../page";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("framer-motion", () => {
  const Passthrough = ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => (
    <div {...(props as object)}>{children}</div>
  );
  const Li = ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => (
    <li {...(props as object)}>{children}</li>
  );
  const Span = ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => (
    <span {...(props as object)}>{children}</span>
  );
  return {
    motion: {
      div: Passthrough,
      li: Li,
      span: Span,
    },
  };
});

const baseFormation = (overrides: Partial<FormationSummary>): FormationSummary => ({
  id: "fmt_test_1",
  llcName: "Test LLC",
  stateCode: "CA",
  status: "draft",
  createdAt: "2026-01-15T12:00:00.000Z",
  ...overrides,
});

/** Tailwind tokens expected on the status badge per `formation-card.tsx` statusBadgeClass */
const statusBadgeColorToken: Record<FormationDashboardStatus, string> = {
  draft: "slate-600",
  pending: "amber-500",
  submitted: "sky-500",
  confirmed: "emerald-500",
  failed: "red-500",
};

const statusLabel: Record<FormationDashboardStatus, string> = {
  draft: "Draft",
  pending: "Pending",
  submitted: "Submitted",
  confirmed: "Confirmed",
  failed: "Failed",
};

describe("dashboard page metadata", () => {
  it("exports metadata with title and description", () => {
    expect(dashboardMetadata.title).toBe("Dashboard — LaunchFree");
    expect(dashboardMetadata.description).toBe(
      "Track your LLC formations and filings."
    );
  });
});

describe("FormationCard", () => {
  it("exports a component", () => {
    expect(typeof FormationCard).toBe("function");
  });

  it("renders LLC name, state, started date, and link to detail", () => {
    render(
      <FormationCard
        formation={baseFormation({
          id: "fmt_abc",
          llcName: "Acme Holdings LLC",
          stateCode: "DE",
          status: "confirmed",
        })}
      />
    );

    expect(screen.getByRole("heading", { name: "Acme Holdings LLC" })).toBeInTheDocument();
    expect(screen.getByText("DE")).toBeInTheDocument();
    expect(screen.getByText(/Started/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Acme Holdings LLC/i });
    expect(link).toHaveAttribute("href", "/dashboard/fmt_abc");
  });

  it("maps each dashboard status to the correct badge color classes", () => {
    const statuses = Object.keys(statusBadgeColorToken) as FormationDashboardStatus[];

    for (const status of statuses) {
      const { unmount } = render(
        <FormationCard formation={baseFormation({ status })} />
      );
      const label = statusLabel[status];
      const badge = screen.getByText(label);
      expect(badge.className).toContain(statusBadgeColorToken[status]);
      unmount();
    }
  });
});

describe("StatusTimeline", () => {
  it("exports a component", () => {
    expect(typeof StatusTimeline).toBe("function");
  });

  it("renders sorted events with descriptions", () => {
    render(
      <StatusTimeline
        events={[
          {
            status: "draft",
            timestamp: "2026-03-01T10:00:00.000Z",
            description: "First step",
          },
          {
            status: "pending",
            timestamp: "2026-03-02T11:00:00.000Z",
            description: "Second step",
          },
        ]}
      />
    );

    expect(screen.getByText("First step")).toBeInTheDocument();
    expect(screen.getByText("Second step")).toBeInTheDocument();
    expect(screen.getByText(/\(current\)/)).toBeInTheDocument();
  });
});
