import type { ReactElement } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminLayoutClient } from "@/app/admin/admin-layout-client";
import { BrainContextProvider } from "@/lib/brain-context";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@clerk/nextjs", () => ({
  UserButton: () => <div data-testid="clerk-user-button-mock" />,
}));

afterEach(() => {
  cleanup();
});

function renderAdmin(ui: ReactElement) {
  return render(<BrainContextProvider>{ui}</BrainContextProvider>);
}

describe("Admin keyboard shortcuts (Cmd+K palette, ? help)", () => {
  it("opens command palette on Meta+K and help on ?", async () => {
    const user = userEvent.setup();
    renderAdmin(
      <AdminLayoutClient founderPending={null} expensesPending={null}>
        <p>page</p>
      </AdminLayoutClient>,
    );

    await user.keyboard("{Meta>}k{/Meta}");

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: /command palette/i })).toBeTruthy();
    });

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /command palette/i })).toBeNull();
    });

    await user.keyboard("?");

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: /keyboard shortcuts/i })).toBeTruthy();
    });
  });
});
