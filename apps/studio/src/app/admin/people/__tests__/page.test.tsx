import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const searchParamsState = vi.hoisted(() => ({
  qs: "",
}));

vi.mock("next/link", () => ({
  default: function MockLink({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) {
    return (
      <a href={href} {...rest}>
        {children}
      </a>
    );
  },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(searchParamsState.qs),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/admin/people",
}));

type AdminPeoplePageFn = (props: {
  searchParams: Promise<{ view?: string }>;
}) => Promise<ReactNode>;

describe("/admin/people", () => {
  beforeEach(() => {
    cleanup();
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv("BRAIN_API_URL", "");
    searchParamsState.qs = "";
  });

  it("default route renders team directory (no workspace tabs)", async () => {
    const mod = (await import("../page")) as { default: AdminPeoplePageFn };
    const tree = await mod.default({
      searchParams: Promise.resolve({}),
    });
    render(tree);
    const directoryLink = screen.getByRole("link", { name: /team directory/i });
    const workspaceLink = screen.getByRole("link", { name: /^workspace$/i });
    expect(directoryLink.getAttribute("href")).toBe("/admin/people");
    expect(workspaceLink.getAttribute("href")).toBe("/admin/people?view=workspace");
    expect(screen.getByPlaceholderText(/filter by name/i)).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "Specs" })).toBeNull();
  });

  it("view=workspace renders PersonasTabsClient shell", async () => {
    searchParamsState.qs = "view=workspace&tab=registry";
    const mod = (await import("../page")) as { default: AdminPeoplePageFn };
    const tree = await mod.default({
      searchParams: Promise.resolve({ view: "workspace" }),
    });
    render(tree);
    await waitFor(
      () => {
        expect(screen.getByRole("tab", { name: "Specs" })).toBeTruthy();
      },
      { timeout: 30_000 },
    );
    expect(screen.queryByPlaceholderText(/filter by name/i)).toBeNull();
  }, 35_000);
});
