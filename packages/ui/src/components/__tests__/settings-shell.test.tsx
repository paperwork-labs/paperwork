import * as React from "react";
import { User } from "lucide-react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

const mockPathname = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

import { SettingsShell, resolveBreadcrumb, type SettingsCluster } from "../settings-shell";

function TestLink({
  href,
  children,
  className,
  scroll: _s,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
  scroll?: boolean;
}) {
  return (
    <a href={href} className={className}>
      {children}
    </a>
  );
}

const clusters: readonly SettingsCluster[] = [
  {
    id: "account",
    label: "Account",
    items: [{ to: "/settings/profile", label: "Profile", icon: User }],
  },
  {
    id: "admin",
    label: "Admin",
    adminOnly: true,
    items: [{ to: "/settings/admin", label: "Admin page", icon: User }],
  },
];

describe("resolveBreadcrumb", () => {
  it("returns cluster and page for exact path", () => {
    expect(resolveBreadcrumb("/settings/profile", clusters)).toEqual({
      cluster: "Account",
      page: "Profile",
    });
  });

  it("returns nested path match", () => {
    expect(resolveBreadcrumb("/settings/profile/edit", clusters)).toEqual({
      cluster: "Account",
      page: "Profile",
    });
  });

  it("returns null when unknown", () => {
    expect(resolveBreadcrumb("/other", clusters)).toBeNull();
  });
});

describe("SettingsShell", () => {
  beforeEach(() => {
    mockPathname.mockReturnValue("/settings/profile");
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("min-width: 48em"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
  });

  it("renders children and nav labels", () => {
    const { getByTestId } = render(
      <SettingsShell clusters={clusters} LinkComponent={TestLink} useAdminGate={() => false}>
        <main data-testid="child">Inner</main>
      </SettingsShell>,
    );
    expect(getByTestId("child")).toHaveTextContent("Inner");
    expect(within(getByTestId("settings-cluster-account")).getByRole("button", { name: "Profile" })).toBeInTheDocument();
    expect(screen.queryByTestId("settings-cluster-admin")).not.toBeInTheDocument();
  });

  it("shows admin cluster when useAdminGate is true", () => {
    mockPathname.mockReturnValue("/settings/admin");
    const { getByTestId } = render(
      <SettingsShell clusters={clusters} LinkComponent={TestLink} useAdminGate={() => true}>
        <div>Admin body</div>
      </SettingsShell>,
    );
    expect(getByTestId("settings-cluster-admin")).toBeInTheDocument();
    expect(within(getByTestId("settings-cluster-admin")).getByRole("button", { name: "Admin page" })).toBeInTheDocument();
  });

  it("uses compact icon nav when viewport is narrow", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: !query.includes("min-width: 48em"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
    mockPathname.mockReturnValue("/settings/profile");
    const { getByLabelText } = render(
      <SettingsShell clusters={clusters} LinkComponent={TestLink} useAdminGate={() => false}>
        <div />
      </SettingsShell>,
    );
    expect(getByLabelText("Settings")).toBeInTheDocument();
  });

  it("renders breadcrumb trail when path matches", () => {
    const { getByTestId } = render(
      <SettingsShell clusters={clusters} LinkComponent={TestLink} settingsHomeHref="/settings/profile">
        <div />
      </SettingsShell>,
    );
    const crumb = getByTestId("settings-breadcrumb");
    expect(crumb).toHaveTextContent("Settings");
    expect(crumb).toHaveTextContent("Account");
    expect(crumb).toHaveTextContent("Profile");
  });
});
