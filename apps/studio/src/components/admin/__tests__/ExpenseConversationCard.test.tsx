import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Conversation } from "@/types/conversations";
import type { Expense } from "@/types/expenses";
import { ExpenseConversationCard } from "../ExpenseConversationCard";

function makeConv(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: "conv-1",
    title: "Expense: Test",
    tags: ["expense-approval"],
    urgency: "normal",
    persona: "cfo",
    participants: [],
    messages: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    status: "needs-action",
    snooze_until: null,
    parent_action_id: null,
    links: { expense_id: "exp-1" },
    ...overrides,
  };
}

const sampleExpense: Expense = {
  id: "exp-1",
  vendor: "Acme",
  amount_cents: 5000,
  currency: "USD",
  category: "infra",
  status: "pending",
  source: "manual",
  classified_by: "founder",
  occurred_at: "2026-04-01",
  submitted_at: new Date().toISOString(),
  approved_at: null,
  reimbursed_at: null,
  notes: "",
  receipt: null,
  tags: [],
  conversation_id: "conv-1",
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("ExpenseConversationCard", () => {
  it("loads expense and POSTs resolve on approve", async () => {
    const resolvedConv = { ...makeConv(), status: "resolved" as const };
    const approvedExp = { ...sampleExpense, status: "approved" as const };

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, data: sampleExpense }),
        text: async () => JSON.stringify({ success: true, data: sampleExpense }),
        status: 200,
        headers: new Headers({ "Content-Type": "application/json" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: { expense: approvedExp, conversation: resolvedConv },
        }),
        text: async () =>
          JSON.stringify({
            success: true,
            data: { expense: approvedExp, conversation: resolvedConv },
          }),
        status: 200,
        headers: new Headers({ "Content-Type": "application/json" }),
      });
    global.fetch = fetchMock;

    const onResolved = vi.fn();
    render(
      <ExpenseConversationCard
        conversationId="conv-1"
        expenseId="exp-1"
        conversation={makeConv()}
        onResolved={onResolved}
      />,
    );

    await waitFor(() => expect(screen.getByText("Acme")).toBeTruthy());

    await userEvent.click(screen.getByTestId("expense-action-approve"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/conversations/conv-1/resolve",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ expense_action: "approve" }),
        }),
      );
    });

    expect(onResolved).toHaveBeenCalledWith({
      expense: approvedExp,
      conversation: resolvedConv,
    });
  });
});
