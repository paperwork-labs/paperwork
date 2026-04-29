import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CursorPaginatedList } from "../cursor-paginated-list";

let ioCallback: IntersectionObserverCallback | null = null;

afterEach(() => {
  ioCallback = null;
  vi.unstubAllGlobals();
});

function installIoMock() {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(cb: IntersectionObserverCallback) {
        ioCallback = cb;
      }
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
      takeRecords() {
        return [];
      }
      root = null;
      rootMargin = "";
      thresholds = [];
    },
  );
}

describe("CursorPaginatedList", () => {
  it("shows loading skeleton before first page resolves", () => {
    installIoMock();
    let resolveFn: (v: { items: string[]; nextCursor: string | null }) => void = () => {};
    const pending = new Promise<{ items: string[]; nextCursor: string | null }>((r) => {
      resolveFn = r;
    });
    render(
      <CursorPaginatedList
        fetchPage={() => pending}
        renderItem={(x) => <span>{x}</span>}
        keyFor={(x) => String(x)}
      />,
    );
    expect(screen.getByLabelText("Loading list")).toBeInTheDocument();
    resolveFn({ items: [], nextCursor: null });
  });

  it("renders default empty state", async () => {
    installIoMock();
    render(
      <CursorPaginatedList
        fetchPage={async () => ({ items: [], nextCursor: null })}
        renderItem={(x) => <span>{String(x)}</span>}
        keyFor={(x) => String(x)}
      />,
    );
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Nothing to show yet."));
  });

  it("renders custom empty state", async () => {
    installIoMock();
    render(
      <CursorPaginatedList
        fetchPage={async () => ({ items: [], nextCursor: null })}
        renderItem={(x) => <span>{String(x)}</span>}
        keyFor={(x) => String(x)}
        emptyState={<div data-testid="empty">No rows</div>}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("empty")).toHaveTextContent("No rows"));
  });

  it("shows error and retries into success", async () => {
    installIoMock();
    const user = userEvent.setup();
    let n = 0;
    const fetchPage = vi.fn(async () => {
      n += 1;
      if (n === 1) throw new Error("network");
      return { items: [7], nextCursor: null };
    });
    render(
      <CursorPaginatedList
        fetchPage={fetchPage}
        renderItem={(x) => <span data-testid="row">{x}</span>}
        keyFor={(x) => String(x)}
      />,
    );
    await waitFor(() => expect(screen.getByText("network")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByTestId("row")).toHaveTextContent("7"));
  });

  it("loads second page when sentinel intersects", async () => {
    installIoMock();
    const fetchPage = vi.fn(async (cursor: string | null) => {
      if (cursor == null) return { items: ["a"], nextCursor: "c1" };
      if (cursor === "c1") return { items: ["b"], nextCursor: null };
      return { items: [], nextCursor: null };
    });
    render(
      <CursorPaginatedList
        fetchPage={fetchPage}
        renderItem={(x) => <span data-testid={`row-${x}`}>{x}</span>}
        keyFor={(x) => String(x)}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("row-a")).toBeInTheDocument());
    expect(ioCallback).toBeTypeOf("function");
    ioCallback?.(
      [{ isIntersecting: true, target: document.createElement("div") } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
    await waitFor(() => expect(screen.getByTestId("row-b")).toBeInTheDocument());
  });

  it("shows inline error when load more fails after first page", async () => {
    installIoMock();
    const fetchPage = vi.fn(async (cursor: string | null) => {
      if (cursor == null) {
        return { items: ["a"], nextCursor: "c1" };
      }
      throw new Error("more failed");
    });
    render(
      <CursorPaginatedList
        fetchPage={fetchPage}
        renderItem={(x) => <span data-testid={`row-${x}`}>{x}</span>}
        keyFor={(x) => String(x)}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("row-a")).toBeInTheDocument());
    ioCallback?.(
      [{ isIntersecting: true, target: document.createElement("div") } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
    await waitFor(() => expect(screen.getByText(/more failed/)).toBeInTheDocument());
  });

  it("uses custom errorState", async () => {
    installIoMock();
    const fetchPage = vi.fn(async () => {
      throw new Error("boom");
    });
    render(
      <CursorPaginatedList
        fetchPage={fetchPage}
        renderItem={(x) => <span>{x}</span>}
        keyFor={(x) => String(x)}
        errorState={(err, retry) => (
          <div data-testid="custom-err">
            {err.message}
            <button type="button" onClick={retry}>
              Go
            </button>
          </div>
        )}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("custom-err")).toHaveTextContent("boom"));
  });
});
