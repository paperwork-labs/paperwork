import * as React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TabbedPageShell, useActiveTab } from "../tabbed-page-shell";

const LazyOne = React.lazy(async () => ({
  default: function One() {
    return <div data-testid="panel-one">One content</div>;
  },
}));

const LazyTwo = React.lazy(async () => ({
  default: function Two() {
    const tab = useActiveTab<"one" | "two">();
    return (
      <div data-testid="panel-two">
        Two content<span data-testid="active">{tab}</span>
      </div>
    );
  },
}));

function ThrowingPanel(): never {
  throw new Error("boom");
}

const LazyThrow = React.lazy(async () => ({
  default: ThrowingPanel,
}));

describe("TabbedPageShell", () => {
  let onTabChange: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    onTabChange = vi.fn();
  });

  it("renders tab labels and shows active panel content", async () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        activeTab="one"
        onTabChange={onTabChange}
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    expect(screen.getByRole("tab", { name: "First" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("panel-one")).toBeInTheDocument());
  });

  it("useActiveTab reflects activeTab prop", async () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        activeTab="two"
        onTabChange={onTabChange}
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("two"));
  });

  it("falls back to defaultTab when activeTab is invalid", async () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        activeTab={"bad" as "one" | "two"}
        onTabChange={onTabChange}
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("panel-one")).toBeInTheDocument());
  });

  it("renders endAdornment when provided", () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        activeTab="one"
        onTabChange={onTabChange}
        endAdornment={<span data-testid="extra">Extra</span>}
        tabs={[{ id: "one", label: "First", Content: LazyOne }]}
      />,
    );
    expect(screen.getByTestId("extra")).toHaveTextContent("Extra");
  });

  it("invokes onTabChange when user activates a tab", async () => {
    const user = userEvent.setup();
    render(
      <TabbedPageShell
        defaultTab="one"
        activeTab="one"
        onTabChange={onTabChange}
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Second" }));
    expect(onTabChange).toHaveBeenCalledWith("two");
  });

  it("ignores invalid tab ids passed up from Tabs", () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        activeTab="one"
        onTabChange={onTabChange}
        tabs={[{ id: "one", label: "First", Content: LazyOne }]}
      />,
    );
    expect(onTabChange).not.toHaveBeenCalled();
  });

  it("shows tab error fallback when lazy panel throws", async () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        activeTab="one"
        onTabChange={onTabChange}
        tabs={[{ id: "one", label: "Broken", Content: LazyThrow }]}
      />,
    );
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("This tab failed to render"),
    );
  });
});

describe("useActiveTab", () => {
  it("throws outside TabbedPageShell", () => {
    function Oops() {
      useActiveTab();
      return null;
    }
    expect(() => render(<Oops />)).toThrow(/useActiveTab must be used within TabbedPageShell/);
  });
});
