import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Conversation, ConversationsListPage } from "@/types/conversations";
import { ConversationsClient } from "../conversations-client";


const navMocks = vi.hoisted(() => ({
  replace: vi.fn(),
  searchParamsHolder: {} as URLSearchParams,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navMocks.replace }),
  usePathname: () => "/admin/brain/conversations",
  useSearchParams: () => navMocks.searchParamsHolder,
}));


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

function emptyResponse(ok = true, status = 200) {
  return {
    ok,
    json: async () => ({ success: true }),
    text: async () => "{}",
    status,
    headers: new Headers(),
  };
}

function createFetchMock(
  listPage: ConversationsListPage,
  extras?: { conversationsById?: Map<string, Conversation> },
): typeof fetch {
  const byId =
    extras?.conversationsById ??
    new Map<string, Conversation>(listPage.items.map((c) => [c.id, c]));

  return vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof Request
          ? input.url
          : String(input);
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/api/admin/conversations/backfill")) {
      return emptyResponse(true, 200);
    }

    const single = /\/api\/admin\/conversations\/([^/?#]+)$/.exec(url);
    if (single && !url.includes("/messages") && method === "GET") {
      const conv = byId.get(single[1]);
      if (!conv) {
        const body = { success: false as const, error: "not found", data: null };
        return {
          ok: false,
          json: async () => body,
          text: async () => JSON.stringify(body),
          status: 404,
          headers: new Headers(),
        };
      }
      const body = { success: true as const, data: conv };
      return {
        ok: true,
        json: async () => body,
        text: async () => JSON.stringify(body),
        status: 200,
        headers: new Headers({ "Content-Type": "application/json" }),
      };
    }

    if (url.includes("/api/admin/conversations?")) {
      const body = { success: true as const, data: listPage };
      return {
        ok: true,
        json: async () => body,
        text: async () => JSON.stringify(body),
        status: 200,
        headers: new Headers({ "Content-Type": "application/json" }),
      };
    }

    const body = {
      success: false as const,
      error: `unhandled fetch: ${method} ${url}`,
    };
    return {
      ok: false,
      json: async () => body,
      text: async () => JSON.stringify(body),
      status: 500,
      headers: new Headers(),
    };
  }) as unknown as typeof fetch;
}

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.resetAllMocks();
  navMocks.searchParamsHolder = new URLSearchParams();
  navMocks.replace.mockClear();
  global.fetch = createFetchMock(makePage([]));
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
    global.fetch = createFetchMock(makePage([conv]));
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
    global.fetch = createFetchMock(makePage([conv]));
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
    global.fetch = createFetchMock(makePage([], 0));
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
    global.fetch = createFetchMock(makePage([openConv]));
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
    global.fetch = createFetchMock(makePage([], 0));

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
    global.fetch = createFetchMock(makePage([conv]));
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


  it("shows chronological thread sub-panel and persona reply form when thread selected", async () => {
    const user = userEvent.setup();
    const older = new Date("2026-04-01T12:00:00.000Z").toISOString();
    const newer = new Date("2026-05-01T12:00:00.000Z").toISOString();
    const msgA = crypto.randomUUID();
    const msgB = crypto.randomUUID();
    const conv = makeConv({
      title: "Threaded inbox",
      messages: [
        {
          id: msgA,
          author: {
            id: "ea",
            kind: "persona",
            display_name: "Executive Assistant",
          },
          body_md: "First message body",
          attachments: [],
          created_at: older,
          reactions: {},
        },
        {
          id: msgB,
          author: {
            id: "cfo",
            kind: "persona",
            display_name: "CFO",
          },
          body_md: "Second reply body",
          attachments: [],
          created_at: newer,
          reactions: {},
        },
      ],
    });

    global.fetch = createFetchMock(makePage([conv]));
    render(
      <ConversationsClient
        brainConfigured
        initialPage={makePage([conv])}
        replyPersonas={[{ id: "cfo", label: "CFO" }, { id: "ea", label: "Executive Assistant" }]}
      />,
    );

    await waitFor(() => expect(screen.getByText("Threaded inbox")).toBeTruthy());
    await user.click(screen.getByText("Threaded inbox"));

    expect(await screen.findByTestId("conversations-thread-subpanel")).toBeTruthy();
    expect(screen.getByTestId("conversations-persona-reply-form")).toBeTruthy();

    const panel = screen.getByTestId("conversations-thread-subpanel");
    const bodies = [...panel.querySelectorAll(".prose")].map((el) => el.textContent ?? "");
    expect(bodies[0]).toContain("First message body");
    expect(bodies[1]).toContain("Second reply body");

    const anchor = panel.querySelector(`[data-msg-id="${msgB}"]`);
    expect(
      anchor?.querySelector('[class*="ring-sky"]'),
    ).toBeTruthy();
  });

  it("opens compose from ?compose=true&persona=cfo with CFO persona checked", async () => {
    navMocks.searchParamsHolder = new URLSearchParams([
      ["compose", "true"],
      ["persona", "cfo"],
    ]);

    render(
      <ConversationsClient
        brainConfigured
        initialPage={makePage([])}
        composePersonaOptions={[{ id: "cfo", label: "Chief Financial Officer" }]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("New conversation")).toBeTruthy();
    });
    await waitFor(() => {
      expect((screen.getByTestId("compose-persona-cfo") as HTMLInputElement).checked).toBe(true);
    });
    expect(navMocks.replace).toHaveBeenCalled();
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
