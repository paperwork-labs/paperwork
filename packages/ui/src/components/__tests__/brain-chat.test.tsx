import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BrainChat } from "../BrainChat";

describe("BrainChat", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { response: "Hello from Brain." },
            }),
        }),
      ),
    );
    Storage.prototype.getItem = vi.fn(() => null);
    Storage.prototype.setItem = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders floating launcher", () => {
    render(
      <BrainChat apiUrl="/api/brain/process" productSlug="test-product" visualVariant="light" />,
    );
    expect(screen.getByTestId("brain-chat-root")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open brain chat/i })).toBeInTheDocument();
  });

  it("expands panel and sends a message", async () => {
    const user = userEvent.setup();
    render(<BrainChat apiUrl="/api/brain/process" productSlug="test-product" />);

    await user.click(screen.getByRole("button", { name: /open brain chat/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/message brain/i)).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/message brain/i), "Ping");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(screen.getByText("Hello from Brain.")).toBeInTheDocument();
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/brain/process",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });
});
