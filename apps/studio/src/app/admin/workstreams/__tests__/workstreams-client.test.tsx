import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import workstreamsJson from "@/data/workstreams.json";
import {
  WorkstreamsFileSchema,
  computeKpis,
} from "@/lib/workstreams/schema";

import { WorkstreamsBoardClient } from "../workstreams-client";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/admin/workstreams",
}));

const parsedFixture = WorkstreamsFileSchema.parse(workstreamsJson);

describe("WorkstreamsBoardClient", () => {
  it("renders KPI strip and seeded titles", () => {
    const kpis = computeKpis(parsedFixture);
    render(
      <WorkstreamsBoardClient kpis={kpis} parsedFile={parsedFixture} />,
    );

    expect(screen.getByRole("heading", { name: /workstreams/i }).textContent).toMatch(
      /workstreams/i,
    );
    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.getByText("Active workstreams")).toBeTruthy();
    expect(screen.getByText("Cancelled")).toBeTruthy();
    expect(screen.getByText("Avg % done")).toBeTruthy();
    expect(screen.getByText(/Track Z · read-only/i)).toBeTruthy();
    expect(screen.getByText(/Cross-cutting work logs across the company/i)).toBeTruthy();
  });

  it("renders stale data banner when provided", () => {
    const kpis = computeKpis(parsedFixture);
    render(
      <WorkstreamsBoardClient
        kpis={kpis}
        parsedFile={parsedFixture}
        staleDataBanner="Live Brain unavailable — showing last build's snapshot from 2026-01-01T00:00:00Z."
      />,
    );
    expect(screen.getByTestId("workstreams-stale-banner").textContent).toMatch(
      /Live Brain unavailable/,
    );
  });

  it("groups completed below incomplete with a 'Completed · N shipped' divider", () => {
    const kpis = computeKpis(parsedFixture);
    const { container } = render(
      <WorkstreamsBoardClient kpis={kpis} parsedFile={parsedFixture} />,
    );

    const completedTotal = parsedFixture.workstreams.filter(
      (w) => w.status === "completed",
    ).length;
    const activeTotal = parsedFixture.workstreams.length - completedTotal;
    expect(completedTotal).toBeGreaterThan(0);
    expect(activeTotal).toBeGreaterThan(0);

    const items = Array.from(container.querySelectorAll("ul[role='list'] > li"));
    const dividerIdx = items.findIndex((el) =>
      el.textContent?.startsWith(`Completed · ${completedTotal} shipped`),
    );
    expect(dividerIdx).toBe(activeTotal);
  });

  it("supports keyboard focus on drag handles (DnD interaction smoke)", async () => {
    const user = userEvent.setup();
    const kpis = computeKpis(parsedFixture);
    render(
      <WorkstreamsBoardClient kpis={kpis} parsedFile={parsedFixture} />,
    );

    const handles = screen.getAllByRole("button", {
      name: /drag to reorder/i,
    });
    expect(handles.length).toBeGreaterThan(1);

    handles[0]?.focus();
    expect(document.activeElement).toBe(handles[0]);

    await user.keyboard("{ArrowDown}");
    await user.keyboard("{ArrowUp}");

    expect(handles[0]).toBeTruthy();
  });
});
