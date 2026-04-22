import React from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@/test/testing-library";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SyncStatusStrip } from "../SyncStatusStrip";
import { usePortfolioAccounts, usePortfolioSync } from "@/hooks/usePortfolio";

vi.mock("@/hooks/usePortfolio", () => ({
  usePortfolioAccounts: vi.fn(),
  usePortfolioSync: vi.fn(),
}));

const usePortfolioAccountsMock = vi.mocked(usePortfolioAccounts);
const usePortfolioSyncMock = vi.mocked(usePortfolioSync);

function Providers({ children, client }: { children: React.ReactNode; client: QueryClient }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

beforeEach(() => {
  usePortfolioSyncMock.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as any);
});

describe("SyncStatusStrip", () => {
  it("returns no container in empty state (not mounted meaningfully)", () => {
    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [],
      refetch: vi.fn(),
    } as any);

    const { container } = render(
      <Providers client={client}>
        <SyncStatusStrip />
      </Providers>
    );
    expect(container.querySelector("[data-testid=sync-status-strip]")).toBeNull();
  });

  it("renders loading skeleton", () => {
    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: true,
      isError: false,
      data: undefined,
      refetch: vi.fn(),
    } as any);

    render(
      <Providers client={client}>
        <SyncStatusStrip />
      </Providers>
    );
    const strip = screen.getByTestId("sync-status-strip");
    expect(strip).toHaveAttribute("data-state", "loading");
  });

  it("renders error with retry", async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: false,
      isError: true,
      error: new Error("network"),
      data: undefined,
      refetch,
    } as any);

    render(
      <Providers client={client}>
        <SyncStatusStrip />
      </Providers>
    );
    expect(screen.getByText("Sync status unavailable")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it("healthy: green overall and youngest age in summary", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-22T12:00:00.000Z"));
    const t1 = "2026-04-22T11:30:00.000Z";
    const t2 = "2026-04-22T11:45:00.000Z";
    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [
        { id: 1, broker: "ibkr", account_number: "U1000001", last_successful_sync: t1, sync_status: "success" },
        { id: 2, broker: "tasty", account_number: "U2000002", last_successful_sync: t2, sync_status: "success" },
      ],
      refetch: vi.fn(),
    } as any);

    render(
      <Providers client={client}>
        <SyncStatusStrip showSyncButton={false} />
      </Providers>
    );
    const strip = screen.getByTestId("sync-status-strip");
    expect(strip).toHaveAttribute("data-overall", "healthy");
    expect(screen.getByText(/all synced · 15m ago/i)).toBeInTheDocument();
  });

  it("stale: amber overall and worst broker label", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-22T20:00:00.000Z"));
    const fresh = "2026-04-22T14:00:00.000Z";
    const old = "2026-04-22T11:00:00.000Z";
    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [
        { id: 1, broker: "ibkr", account_number: "U1000001", last_successful_sync: fresh, sync_status: "success" },
        { id: 2, broker: "tasty", account_number: "U2000002", last_successful_sync: old, sync_status: "success" },
      ],
      refetch: vi.fn(),
    } as any);

    render(
      <Providers client={client}>
        <SyncStatusStrip showSyncButton={false} />
      </Providers>
    );
    const strip = screen.getByTestId("sync-status-strip");
    expect(strip).toHaveAttribute("data-overall", "stale");
    expect(screen.getByText(/TASTY stale ·/i)).toBeInTheDocument();
  });

  it("failed: red overall and count", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-22T20:00:00.000Z"));
    const tOld = "2026-04-22T02:00:00.000Z";
    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [
        { id: 1, broker: "ibkr", account_number: "A1", last_successful_sync: null, sync_status: "never_synced" },
        { id: 2, broker: "ibkr", account_number: "A2", last_successful_sync: tOld, sync_status: "error" },
        { id: 3, broker: "tasty", account_number: "A3", last_successful_sync: tOld, sync_status: "success" },
      ],
      refetch: vi.fn(),
    } as any);

    render(
      <Providers client={client}>
        <SyncStatusStrip showSyncButton={false} />
      </Providers>
    );
    const strip = screen.getByTestId("sync-status-strip");
    expect(strip).toHaveAttribute("data-overall", "failed");
    expect(screen.getByText(/2 accounts sync failed/i)).toBeInTheDocument();
  });

  it("opens popover and lists brokers", async () => {
    // Real timers here: Radix Popover animations + userEvent don't play nicely with vi.useFakeTimers().
    const t = new Date(Date.now() - 60 * 60 * 1000).toISOString();
    const user = userEvent.setup();
    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [
        { id: 1, broker: "ibkr", account_number: "U1000001", last_successful_sync: t, sync_status: "success" },
        { id: 2, broker: "tasty", account_number: "U2000002", last_successful_sync: t, sync_status: "success" },
        { id: 3, broker: "schwab", account_number: "U3000003", last_successful_sync: t, sync_status: "success" },
      ],
      refetch: vi.fn(),
    } as any);

    render(
      <Providers client={client}>
        <SyncStatusStrip showSyncButton={false} />
      </Providers>
    );
    await user.click(screen.getByRole("button", { name: /account sync details/i }));
    await waitFor(() => {
      expect(screen.getByText("Accounts")).toBeInTheDocument();
    });
    expect(screen.getByText(/IBKR ···0001/)).toBeInTheDocument();
    expect(screen.getByText(/TASTY ···0002/)).toBeInTheDocument();
    expect(screen.getByText(/SCHWAB ···0003/)).toBeInTheDocument();
  });

  it("Sync triggers usePortfolioSync mutate", async () => {
    // Real timers: see comment on popover test above.
    const t = new Date(Date.now() - 30 * 60 * 1000).toISOString();
    const user = userEvent.setup();
    const mutate = vi.fn();
    usePortfolioSyncMock.mockReturnValue({
      mutate,
      isPending: false,
    } as any);

    const client = new QueryClient();
    usePortfolioAccountsMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [{ id: 1, broker: "ibkr", account_number: "U1", last_successful_sync: t, sync_status: "success" }],
      refetch: vi.fn(),
    } as any);

    render(
      <Providers client={client}>
        <SyncStatusStrip showSyncButton />
      </Providers>
    );
    await user.click(
      screen.getByRole("button", {
        name: "Sync",
      })
    );
    expect(mutate).toHaveBeenCalled();
  });
});
