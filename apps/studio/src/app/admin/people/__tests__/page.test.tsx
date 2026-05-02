import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EmployeeListItem } from "@/lib/brain-client";

const searchParamsState = vi.hoisted(() => ({
  qs: "",
}));

const { mockGetEmployees } = vi.hoisted(() => ({
  mockGetEmployees: vi.fn(),
}));

vi.mock("@/lib/brain-client", () => {
  class BrainClientError extends Error {
    readonly status: number;
    readonly endpoint: string;
    constructor(endpoint: string, status: number, detail: string) {
      super(detail);
      this.name = "BrainClientError";
      this.endpoint = endpoint;
      this.status = status;
    }
  }
  class BrainClient {
    static fromEnv() {
      return new BrainClient();
    }
    getEmployees() {
      return mockGetEmployees() as Promise<EmployeeListItem[]>;
    }
  }
  return { BrainClient, BrainClientError };
});

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

const sampleRoster: EmployeeListItem[] = [
  {
    slug: "founder",
    kind: "human",
    role_title: "Principal",
    team: "Executive Council",
    display_name: "Founder Name",
    tagline: "Sets direction",
    avatar_emoji: "🧭",
    named_at: "2026-01-01T00:00:00Z",
    named_by_self: false,
    reports_to: null,
  },
  {
    slug: "helper-bot",
    kind: "ai_persona",
    role_title: "Assistant",
    team: "Engineering",
    display_name: "Helper",
    tagline: "Ships small fixes",
    avatar_emoji: "🤖",
    named_at: null,
    named_by_self: true,
    reports_to: "founder",
  },
];

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
    mockGetEmployees.mockResolvedValue(sampleRoster);
  });

  it("default route renders directory (org grid from Brain employees)", async () => {
    const mod = (await import("../page")) as { default: AdminPeoplePageFn };
    const tree = await mod.default({
      searchParams: Promise.resolve({}),
    });
    render(tree);
    const directoryLink = screen.getByRole("link", { name: /^directory$/i });
    const workspaceLink = screen.getByRole("link", { name: /^workspace$/i });
    expect(directoryLink.getAttribute("href")).toBe("/admin/people");
    expect(workspaceLink.getAttribute("href")).toBe("/admin/people?view=workspace");
    expect(screen.getByRole("heading", { name: "People", level: 1 })).toBeTruthy();
    expect(screen.getByText("Founder Name")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Helper/ }).getAttribute("href")).toBe(
      "/admin/people/helper-bot",
    );
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
    expect(screen.queryByText("Founder Name")).toBeNull();
  }, 35_000);
});
