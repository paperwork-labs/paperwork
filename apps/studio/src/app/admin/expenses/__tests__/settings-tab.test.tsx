import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import type { ExpenseRoutingRules } from "@/types/expenses";
import { SettingsTab } from "../settings-tab";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const baseRules: ExpenseRoutingRules = {
  auto_approve_threshold_cents: 0,
  auto_approve_categories: [],
  always_review_categories: [],
  flag_amount_cents_above: 100000,
  founder_card_default_source: "founder-card",
  subscription_skip_approval: false,
  updated_at: "2026-04-01T00:00:00Z",
  updated_by: "founder",
  history: [
    {
      at: "2026-04-02T00:00:00Z",
      updated_by: "founder",
      diff: { auto_approve_threshold_cents: { from: 0, to: 10000 } },
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ success: true, data: { items: [], total: 0, has_more: false } }),
    text: async () => "{}",
    status: 200,
    headers: new Headers(),
  });
});

describe("SettingsTab", () => {
  it("formats threshold in dollars and shows history", async () => {
    render(<SettingsTab rules={baseRules} />);

    await waitFor(() => expect(screen.getByLabelText(/threshold/i)).toBeTruthy());

    const th = screen.getByLabelText(/threshold/i) as HTMLInputElement;
    expect(th.value).toBe("0");

    expect(screen.getByText(/Recent changes/i)).toBeTruthy();
    expect(screen.getByText(/auto_approve_threshold_cents/i)).toBeTruthy();
  });

  it("disables save until dirty and PUTs rules on submit", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, data: { items: [], total: 0, has_more: false } }),
        text: async () => "{}",
        status: 200,
        headers: new Headers(),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: { ...baseRules, auto_approve_threshold_cents: 50000 },
        }),
        text: async () => "{}",
        status: 200,
        headers: new Headers(),
      });

    const onSaved = vi.fn();
    render(<SettingsTab rules={baseRules} onRulesSaved={onSaved} />);

    const saveBtn = await screen.findByTestId("settings-save-rules");
    expect((saveBtn as HTMLButtonElement).disabled).toBe(true);

    await userEvent.clear(screen.getByLabelText(/threshold/i));
    await userEvent.type(screen.getByLabelText(/threshold/i), "500");

    const saveBtnEnabled = await screen.findByTestId("settings-save-rules");
    expect((saveBtnEnabled as HTMLButtonElement).disabled).toBe(false);

    await userEvent.click(saveBtnEnabled);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/expenses/rules",
        expect.objectContaining({
          method: "PUT",
        }),
      );
    });
    expect(onSaved).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith(
      "Rules updated · audit Conversation created",
      expect.any(Object),
    );
  });

  it("renders auto-approve and always-review chip sections", async () => {
    render(<SettingsTab rules={baseRules} />);
    expect(await screen.findByTestId("settings-auto-categories")).toBeTruthy();
    expect(screen.getByTestId("settings-always-categories")).toBeTruthy();
  });
});
