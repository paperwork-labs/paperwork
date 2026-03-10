import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CurrencyDisplay } from "./currency-display";

describe("CurrencyDisplay", () => {
  it("renders formatted dollars from cents without animation", () => {
    render(<CurrencyDisplay cents={123456} animate={false} />);
    expect(screen.getByText(/1,234\.56/)).toBeInTheDocument();
  });

  it("renders zero correctly", () => {
    render(<CurrencyDisplay cents={0} animate={false} />);
    expect(screen.getByText(/0\.00/)).toBeInTheDocument();
  });

  it("renders small amounts", () => {
    render(<CurrencyDisplay cents={1} animate={false} />);
    expect(screen.getByText(/0\.01/)).toBeInTheDocument();
  });

  it("uses custom prefix", () => {
    render(<CurrencyDisplay cents={5000} animate={false} prefix="-$" />);
    expect(screen.getByText(/-\$/)).toBeInTheDocument();
    expect(screen.getByText(/50\.00/)).toBeInTheDocument();
  });

  it("applies custom className", () => {
    render(
      <CurrencyDisplay cents={100} animate={false} className="text-green-400" />
    );
    const el = screen.getByText(/1\.00/);
    expect(el).toHaveClass("text-green-400");
  });

  it("starts at 0 when animate is true then reaches target", async () => {
    vi.useFakeTimers();
    render(<CurrencyDisplay cents={10000} animate duration={400} />);

    expect(screen.getByText(/0\.00/)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByText(/100\.00/)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("renders large amounts with comma separators", () => {
    render(<CurrencyDisplay cents={100_000_00} animate={false} />);
    expect(screen.getByText(/100,000\.00/)).toBeInTheDocument();
  });
});
