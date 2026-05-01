import { cleanup, render, screen, waitFor, act, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Conversation, ConversationsListPage } from "@/types/conversations";

const searchParamsState = vi.hoisted(() => ({
  qs: "",
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(searchParamsState.qs),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/admin/brain/conversations",
}));

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
  cleanup();
  vi.resetAllMocks();
  searchParamsState.qs = "";
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

  it("renders inline setup warning for disk/backfill issues without blocking inbox", async () => {
    const conv = makeConv({ title: "Visible thread" });
    global.fetch = mockFetch(makePage([conv]));
    render(
      <ConversationsClient
        brainConfigured
        initialPage={makePage([conv])}
        setupWarning="founder-actions.json not found on disk (expected under apps/studio/src/data/)."
      />,
    );
    expect(screen.getByTestId("conversations-setup-warning")).toBeTruthy();
    expect(screen.queryByTestId("conversations-setup-error")).toBeNull();
    await waitFor(() => {
      expect(screen.getByText("Visible thread")).toBeTruthy();
    });
  });

  it("renders setup error with retry when inbox failed to load", () => {
    render(
      <ConversationsClient
        brainConfigured
        initialPage={null}
        setupError="Failed to load conversations (503)"
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

  it("clicking a message opens thread sub-panel with messages and reply form", async () => {
    const user = userEvent.setup();
    const rootId = "fixture-msg-root";
    const replyId = "fixture-msg-reply";
    const conv = makeConv({
      messages: [
        {
          id: rootId,
          author: { id: "founder", kind: "founder", display_name: "Founder" },
          body_md: "Root content",
          attachments: [],
          created_at: "2026-01-01T12:00:00.000Z",
          reactions: {},
          parent_message_id: null,
        },
        {
          id: replyId,
          author: { id: "cfo", kind: "persona", display_name: "CFO Persona" },
          body_md: "Nested reply text",
          attachments: [],
          created_at: "2026-01-02T12:00:00.000Z",
          reactions: {},
          parent_message_id: rootId,
        },
      ],
    });
    global.fetch = mockFetch(makePage([conv]));
    render(
      <ConversationsClient
        brainConfigured
        initialPage={makePage([conv])}
        replyPersonas={[{ id: "cfo", label: "CFO" }]}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("Test conversation")).toBeTruthy();
    });
    await user.click(screen.getByText("Test conversation"));
    await user.click(screen.getByTestId(`conversation-message-${replyId}`));

    await waitFor(() => {
      expect(screen.getByTestId("conversation-thread-subpanel")).toBeTruthy();
    });
    const panel = screen.getByTestId("conversation-thread-subpanel");
    expect(within(panel).getByText("Root content")).toBeTruthy();
    expect(within(panel).getByText("Nested reply text")).toBeTruthy();
    expect(panel.querySelector('textarea[placeholder="Write your reply..."]')).toBeTruthy();
    expect(within(panel).getByTestId("thread-panel-reply-form")).toBeTruthy();
  });

  it("?compose=true&persona=cfo opens compose modal with CFO participant checked", async () => {
    searchParamsState.qs = "compose=true&persona=cfo";
    render(
      <ConversationsClient
        brainConfigured
        initialPage={makePage([])}
        composePersonaOptions={[
          { id: "cfo", label: "CFO" },
          { id: "ea", label: "EA" },
        ]}
      />,
    );
    await waitFor(() => {
      expect(screen.getAllByTestId("compose-modal").length).toBeGreaterThanOrEqual(1);
    });
    const modal = screen.getAllByTestId("compose-modal")[0]!;
    const cfo = within(modal).getByTestId("compose-persona-cfo") as HTMLInputElement;
    expect(cfo.checked).toBe(true);
  });
});
