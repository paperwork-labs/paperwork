import * as React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const replace = vi.fn();
let searchParams = new URLSearchParams("tab=one");

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/portfolio",
  useSearchParams: () => searchParams,
}));

import { TabbedPageShell, useActiveTab } from "../tabbed-page-shell";

function ThrowingPanel(): never {
  throw new Error("boom");
}

const LazyThrow = React.lazy(async () => ({
  default: ThrowingPanel,
}));

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

describe("TabbedPageShell", () => {
  beforeEach(() => {
    replace.mockClear();
    searchParams = new URLSearchParams("tab=one");
  });

  it("renders tab labels and shows active panel content", async () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    expect(screen.getByRole("tab", { name: "First" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("panel-one")).toBeInTheDocument());
  });

  it("useActiveTab reflects resolved tab id", async () => {
    searchParams = new URLSearchParams("tab=two");
    render(
      <TabbedPageShell
        defaultTab="one"
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("two"));
  });

  it("renders endAdornment when provided", () => {
    render(
      <TabbedPageShell
        defaultTab="one"
        endAdornment={<span data-testid="extra">Extra</span>}
        tabs={[{ id: "one", label: "First", Content: LazyOne }]}
      />,
    );
    expect(screen.getByTestId("extra")).toHaveTextContent("Extra");
  });

  it("seeds default tab in URL when param missing", async () => {
    searchParams = new URLSearchParams("");
    render(
      <TabbedPageShell
        defaultTab="one"
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    await waitFor(() => expect(replace).toHaveBeenCalled());
  });

  it("normalizes invalid tab query via router.replace", async () => {
    searchParams = new URLSearchParams("tab=bad");
    render(
      <TabbedPageShell
        defaultTab="one"
        tabs={[
          { id: "one", label: "First", Content: LazyOne },
          { id: "two", label: "Second", Content: LazyTwo },
        ]}
      />,
    );
    await waitFor(() => expect(replace).toHaveBeenCalled());
  });

  it("shows tab error fallback when lazy panel throws", async () => {
    searchParams = new URLSearchParams("tab=one");
    render(
      <TabbedPageShell
        defaultTab="one"
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
