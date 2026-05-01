import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  AutopilotActions,
  AutopilotActionsIfPending,
} from "../autopilot-actions-client";

const approveDispatch = vi.fn();
const vetoDispatch = vi.fn();

vi.mock("../actions", () => ({
  approveDispatch: (...args: unknown[]) => approveDispatch(...args),
  vetoDispatch: (...args: unknown[]) => vetoDispatch(...args),
}));

describe("AutopilotActionsIfPending", () => {
  it("renders approve/veto only for pending status", () => {
    const { rerender } = render(
      <AutopilotActionsIfPending status="pending" taskId="42" />,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeTruthy();

    rerender(<AutopilotActionsIfPending status="completed" taskId="42" />);
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
  });
});

describe("AutopilotActions", () => {
  it("calls approveDispatch with task id when Approve is clicked", async () => {
    approveDispatch.mockResolvedValue({ ok: true });
    const user = userEvent.setup();
    render(<AutopilotActions taskId="99" />);

    await user.click(screen.getByRole("button", { name: /approve/i }));

    expect(approveDispatch).toHaveBeenCalledTimes(1);
    expect(approveDispatch).toHaveBeenCalledWith("99");
  });
});
