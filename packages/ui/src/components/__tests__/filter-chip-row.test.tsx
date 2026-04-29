import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FilterChipRow } from "../filter-chip-row";

describe("FilterChipRow", () => {
  it("shows empty state when no chips", () => {
    render(<FilterChipRow chips={[]} value="x" onChange={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("No filters available");
  });

  it("calls onChange when chip clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FilterChipRow
        chips={[
          { id: "a", label: "Alpha" },
          { id: "b", label: "Beta", count: 3 },
        ]}
        value="a"
        onChange={onChange}
      />,
    );
    await user.click(screen.getByText("Beta"));
    expect(onChange).toHaveBeenCalledWith("b");
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders solid variant active styling", () => {
    render(
      <FilterChipRow
        variant="solid"
        chips={[{ id: "x", label: "X" }]}
        value="x"
        onChange={() => {}}
      />,
    );
    const chip = screen.getByRole("radio", { name: "X" });
    expect(chip).toHaveAttribute("aria-checked", "true");
  });

  it("renders endAdornment", () => {
    render(
      <FilterChipRow
        chips={[{ id: "a", label: "A" }]}
        value="a"
        onChange={() => {}}
        endAdornment={<span data-testid="end">End</span>}
      />,
    );
    expect(screen.getByTestId("end")).toHaveTextContent("End");
  });
});
