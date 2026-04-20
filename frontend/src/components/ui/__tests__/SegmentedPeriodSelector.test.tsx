import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SegmentedPeriodSelector } from "../SegmentedPeriodSelector";

const PERIODS = [
  { value: "1D", label: "1D" },
  { value: "1W", label: "1W" },
  { value: "1M", label: "1M" },
  { value: "3M", label: "3M" },
  { value: "1Y", label: "1Y" },
] as const;

function Harness({ initial = "1W" }: { initial?: string }) {
  const [v, setV] = React.useState<string>(initial);
  return (
    <SegmentedPeriodSelector
      ariaLabel="Time period"
      options={PERIODS}
      value={v}
      onChange={setV}
    />
  );
}

describe("SegmentedPeriodSelector", () => {
  it("renders as a radiogroup with all options", () => {
    render(<Harness />);
    const group = screen.getByRole("radiogroup", { name: /time period/i });
    expect(group).toBeInTheDocument();
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(PERIODS.length);
  });

  it("marks the active option via aria-checked", () => {
    render(<Harness initial="1M" />);
    const radio = screen.getByRole("radio", { name: "1M" });
    expect(radio).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "1D" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("only the active option has tabIndex=0 (roving tabindex)", () => {
    render(<Harness initial="1M" />);
    expect(
      (screen.getByRole("radio", { name: "1M" }) as HTMLButtonElement).tabIndex,
    ).toBe(0);
    expect(
      (screen.getByRole("radio", { name: "1D" }) as HTMLButtonElement).tabIndex,
    ).toBe(-1);
  });

  it("clicking a segment fires onChange", () => {
    const onChange = vi.fn();
    render(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value="1W"
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole("radio", { name: "3M" }));
    expect(onChange).toHaveBeenCalledWith("3M");
  });

  it("ArrowRight selects the next option (and wraps)", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value="1W"
        onChange={onChange}
      />,
    );
    const active = screen.getByRole("radio", { name: "1W" });
    fireEvent.keyDown(active, { key: "ArrowRight" });
    expect(onChange).toHaveBeenLastCalledWith("1M");

    rerender(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value="1Y"
        onChange={onChange}
      />,
    );
    fireEvent.keyDown(screen.getByRole("radio", { name: "1Y" }), {
      key: "ArrowRight",
    });
    expect(onChange).toHaveBeenLastCalledWith("1D");
  });

  it("ArrowLeft selects the previous option (and wraps)", () => {
    const onChange = vi.fn();
    render(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value="1D"
        onChange={onChange}
      />,
    );
    fireEvent.keyDown(screen.getByRole("radio", { name: "1D" }), {
      key: "ArrowLeft",
    });
    expect(onChange).toHaveBeenLastCalledWith("1Y");
  });

  it("Home/End jump to first/last", () => {
    const onChange = vi.fn();
    render(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value="1M"
        onChange={onChange}
      />,
    );
    fireEvent.keyDown(screen.getByRole("radio", { name: "1M" }), {
      key: "End",
    });
    expect(onChange).toHaveBeenLastCalledWith("1Y");
    fireEvent.keyDown(screen.getByRole("radio", { name: "1M" }), {
      key: "Home",
    });
    expect(onChange).toHaveBeenLastCalledWith("1D");
  });

  it("makes the first option tabbable when controlled value is missing (regression for D1)", () => {
    // Previously: every button got tabIndex=-1, leaving the radiogroup
    // unreachable by keyboard until the parent supplied a real value.
    const onChange = vi.fn();
    render(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value={"unknown" as unknown as (typeof PERIODS)[number]["value"]}
        onChange={onChange}
      />,
    );
    const radios = screen.getAllByRole("radio") as HTMLButtonElement[];
    // First option is the fallback tabbable.
    expect(radios[0].tabIndex).toBe(0);
    // No option should be aria-checked because value is indeterminate.
    radios.forEach((r) => expect(r).toHaveAttribute("aria-checked", "false"));
    // Other options are not tabbable.
    expect(radios[1].tabIndex).toBe(-1);
  });

  it("uses focus-visible classes (not focus:outline-none) so the global focus ring is preserved (regression for D2)", () => {
    render(<Harness />);
    const radio = screen.getByRole("radio", { name: "1D" }) as HTMLButtonElement;
    const cls = radio.className;
    expect(cls).toMatch(/focus-visible:outline-none/);
    expect(cls).toMatch(/focus-visible:ring-2/);
    expect(cls).not.toMatch(/(?<!focus-visible:)focus:outline-none/);
  });

  it("respects controlled value when re-rendered", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value="1W"
        onChange={onChange}
      />,
    );
    expect(screen.getByRole("radio", { name: "1W" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    rerender(
      <SegmentedPeriodSelector
        ariaLabel="Time period"
        options={PERIODS}
        value="3M"
        onChange={onChange}
      />,
    );
    expect(screen.getByRole("radio", { name: "3M" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});
