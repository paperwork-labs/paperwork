import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HqMissingCredCard } from "./HqMissingCredCard";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

afterEach(() => {
  cleanup();
});

describe("HqMissingCredCard", () => {
  it("renders service, env var, and reconnect", () => {
    render(
      <HqMissingCredCard
        service="GitHub"
        envVar="GITHUB_TOKEN"
        reconnectAction={{ label: "Reconnect", href: "https://example.com/env" }}
      />,
    );
    const card = screen.getByTestId("hq-missing-cred-card");
    expect(within(card).getByText(/GitHub · missing/i)).toBeTruthy();
    expect(within(card).getByText("GITHUB_TOKEN")).toBeTruthy();
    const link = within(card).getByRole("link", { name: "Reconnect" });
    expect(link.getAttribute("href")).toBe("https://example.com/env");
  });
});
