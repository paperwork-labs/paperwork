import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ErrorState } from "../ErrorState";

const ORIGINAL_DEV = import.meta.env.DEV;

afterEach(() => {
  // Vitest's `import.meta.env` is mutable in tests; restore between cases.
  (import.meta.env as { DEV: boolean }).DEV = ORIGINAL_DEV;
});

describe("ErrorState", () => {
  it("renders the title and description with role=alert", () => {
    render(
      <ErrorState
        title="Failed to load chart"
        description="The market data service is unreachable."
      />,
    );
    const root = screen.getByRole("alert");
    expect(root).toBeInTheDocument();
    expect(root).toHaveTextContent("Failed to load chart");
    expect(root).toHaveTextContent("market data service");
  });

  it("invokes retry on click", () => {
    const retry = vi.fn();
    render(<ErrorState title="Oops" retry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("uses a custom retry label when supplied", () => {
    render(<ErrorState title="Oops" retry={() => undefined} retryLabel="Refresh" />);
    expect(screen.getByRole("button", { name: /refresh/i })).toBeInTheDocument();
  });

  it("does NOT show the error details block when DEV=false", () => {
    (import.meta.env as { DEV: boolean }).DEV = false;
    render(
      <ErrorState
        title="Boom"
        error={new Error("internal stack trace that should be hidden")}
      />,
    );
    expect(
      screen.queryByText(/internal stack trace that should be hidden/i),
    ).toBeNull();
    expect(screen.queryByText(/show error details/i)).toBeNull();
  });

  it("shows the error details block when DEV=true", () => {
    (import.meta.env as { DEV: boolean }).DEV = true;
    render(
      <ErrorState
        title="Boom"
        error={new Error("dev-visible failure")}
      />,
    );
    expect(screen.getByText(/show error details/i)).toBeInTheDocument();
    expect(screen.getByText(/dev-visible failure/)).toBeInTheDocument();
  });

  it("formats non-Error values as JSON in dev mode", () => {
    (import.meta.env as { DEV: boolean }).DEV = true;
    render(
      <ErrorState
        title="Boom"
        error={{ code: 500, msg: "downstream failure" }}
      />,
    );
    expect(screen.getByText(/downstream failure/)).toBeInTheDocument();
  });
});
