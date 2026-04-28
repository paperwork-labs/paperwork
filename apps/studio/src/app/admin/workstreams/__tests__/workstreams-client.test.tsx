import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import workstreamsJson from "@/data/workstreams.json";
import {
  WorkstreamsFileSchema,
  computeKpis,
} from "@/lib/workstreams/schema";

import { WorkstreamsBoardClient } from "../workstreams-client";

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
    expect(screen.getByText("Avg % done")).toBeTruthy();
    expect(
      screen.getByText(/Workstreams board \(Track Z\)/i),
    ).toBeTruthy();
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
