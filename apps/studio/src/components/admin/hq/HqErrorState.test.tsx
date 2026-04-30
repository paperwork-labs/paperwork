import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HqErrorState } from "./HqErrorState";

afterEach(() => {
  cleanup();
});

describe("HqErrorState", () => {
  it("renders without crash", () => {
    render(<HqErrorState />);
    expect(screen.getByTestId("hq-error-state")).toBeTruthy();
  });

  it("toggles error details", async () => {
    const user = userEvent.setup();
    render(<HqErrorState error={new Error("boom")} />);
    expect(screen.queryByText(/Error:\s*boom/)).toBeNull();
    await user.click(screen.getByRole("button", { name: /show details/i }));
    expect(screen.getByText(/Error:\s*boom/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /hide details/i }));
  });

  it("calls onRetry when provided", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<HqErrorState onRetry={onRetry} />);
    await user.click(screen.getByRole("button", { name: /^retry$/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
