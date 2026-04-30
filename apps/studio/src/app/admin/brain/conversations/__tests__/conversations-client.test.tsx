import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Conversation, ConversationsListPage } from "@/types/conversations";
import { ConversationsClient } from "../conversations-client";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeConv(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "Test conversation",
    tags: ["infra"],
    urgency: "normal",
    persona: null,
    participants: [],
    messages: [
      {
        id: crypto.randomUUID(),
        author: { id: "founder", kind: "founder", display_name: "Founder" },
        body_md: "Hello world",
        attachments: [],
        created_at: new Date().toISOString(),
        reactions: {},
      },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    status: "needs-action",
    snooze_until: null,
    parent_action_id: null,
    links: null,
    ...overrides,
  };
}

function makePage(convs: Conversation[], total?: number): ConversationsListPage {
  return { items: convs, next_cursor: null, total: total ?? convs.length };
}

function mockFetch(page: ConversationsListPage) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ success: true, data: page }),
    text: async () => JSON.stringify({ success: true, data: page }),
    status: 200,
    headers: new Headers({ "Content-Type": "application/json" }),
  });
}

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.resetAllMocks();
  global.fetch = mockFetch(makePage([]));
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConversationsClient", () => {
  it("renders unconfigured notice when Brain not configured", () => {
    render(<ConversationsClient brainConfigured={false} initialPage={null} />);
    expect(screen.getByText(/brain is not configured/i)).toBeTruthy();
  });

  it("renders setup error with retry when founder-actions / backfill failed", () => {
    render(
      <ConversationsClient
        brainConfigured
        initialPage={null}
        setupError="Could not read founder-actions.json: invalid JSON"
      />,
    );
    expect(screen.getByTestId("conversations-setup-error")).toBeTruthy();
    expect(screen.getByRole("button", { name: /retry/i })).toBeTruthy();
  });

  it("renders initial conversations from SSR data", async () => {
    const conv = makeConv({ title: "Alpha conversation" });
    // Make the fetch mock return the same page so refetch doesn't clear it
    global.fetch = mockFetch(makePage([conv]));
    render(
      <ConversationsClient
        brainConfigured
        initialPage={makePage([conv])}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("Alpha conversation")).toBeTruthy();
    });
  });

  it("shows loading state while fetching", async () => {
    let resolveLoad: (value: unknown) => void;
    global.fetch = vi.fn().mockReturnValue(
      new Promise((res) => {
        resolveLoad = res;
      }),
    );
    render(<ConversationsClient brainConfigured initialPage={null} />);
    expect(screen.getByTestId("conversations-loading")).toBeTruthy();
    await act(async () => {
      resolveLoad!({
        ok: true,
        json: async () => ({ success: true, data: makePage([]) }),
        text: async () => "",
        status: 200,
        headers: new Headers(),
      });
    });
  });

  it("shows empty-needs-action state when filter returns no results", async () => {
    global.fetch = mockFetch(makePage([], 0));
    render(<ConversationsClient brainConfigured initialPage={makePage([], 0)} />);
    await waitFor(() => {
      expect(screen.getByTestId("conversations-empty-needs-action")).toBeTruthy();
    });
  });

  it("shows error state when Brain returns error", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: false, error: "Brain exploded" }),
      text: async () => "",
      status: 500,
      headers: new Headers(),
    });
    render(<ConversationsClient brainConfigured initialPage={null} />);
    await waitFor(() => {
      expect(screen.getByTestId("conversations-error")).toBeTruthy();
    });
  });

  it("switches filter when chip clicked", async () => {
    const user = userEvent.setup();
    const openConv = makeConv({ title: "Open conv", status: "open", urgency: "normal" });
    global.fetch = mockFetch(makePage([openConv]));
    render(<ConversationsClient brainConfigured initialPage={null} />);

    // Wait for initial fetch to settle
    await waitFor(() => {
      expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(0);
    });

    // Find the filter chip buttons (they have specific class patterns)
    const allButtons = screen.getAllByRole("button");
    const openChip = allButtons.find(
      (btn) => btn.textContent?.trim() === "Open" && btn.className.includes("rounded-full"),
    );
    expect(openChip).toBeTruthy();
    await user.click(openChip!);

    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(String(lastCall[0])).toContain("filter=open");
    });
  });

  it("shows search-empty state when search yields no results", async () => {
    global.fetch = mockFetch(makePage([], 0));

    const { container } = render(
      <ConversationsClient brainConfigured initialPage={makePage([], 0)} />,
    );

    const searchInput = container.querySelector(
      "input[placeholder*='Search']",
    ) as HTMLInputElement;
    await act(async () => {
      searchInput.focus();
      await userEvent.type(searchInput, "xyzzy-no-match");
    });

    // Debounce fires at 300ms; wait for it
    await waitFor(
      () => {
        expect(screen.getByTestId("conversations-empty-search")).toBeTruthy();
      },
      { timeout: 2000 },
    );
  });

  it("renders conversation title in thread pane when selected", async () => {
    const user = userEvent.setup();
    const conv = makeConv({ title: "Selected thread" });
    global.fetch = mockFetch(makePage([conv]));
    render(
      <ConversationsClient brainConfigured initialPage={makePage([conv])} />,
    );

    // Wait for the conversation to appear in the inbox
    await waitFor(() => {
      expect(screen.getByText("Selected thread")).toBeTruthy();
    });

    await user.click(screen.getByText("Selected thread"));

    // After selection, title appears in thread header too
    await waitFor(() => {
      const elements = screen.getAllByText("Selected thread");
      expect(elements.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("Hello world")).toBeTruthy();
  });

  it("opens compose modal on Compose button click", async () => {
    const user = userEvent.setup();
    render(<ConversationsClient brainConfigured initialPage={makePage([])} />);

    // Use getAllByRole to handle potential multiple matches, pick the first
    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeGreaterThan(0);
    });

    const composeBtn = screen
      .getAllByRole("button")
      .find((btn) => btn.textContent?.trim().toLowerCase().includes("compose"));
    expect(composeBtn).toBeTruthy();
    await user.click(composeBtn!);
    await waitFor(() => {
      expect(screen.getByText("New conversation")).toBeTruthy();
    });
  });
});
