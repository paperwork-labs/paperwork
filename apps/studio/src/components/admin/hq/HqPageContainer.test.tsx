import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { HqPageContainer } from "./HqPageContainer";

afterEach(() => {
  cleanup();
});

describe("HqPageContainer", () => {
  it("renders children", () => {
    render(
      <HqPageContainer>
        <p data-testid="child">hello</p>
      </HqPageContainer>,
    );
    expect(screen.getByTestId("child").textContent).toBe("hello");
  });

  it("applies default max width (960px)", () => {
    const { container } = render(
      <HqPageContainer>
        <span />
      </HqPageContainer>,
    );
    const el = container.firstElementChild as HTMLElement;
    expect(el.className).toContain("max-w-[960px]");
    expect(el.className).toContain("mx-auto");
    expect(el.className).toContain("px-4");
    expect(el.className).toContain("md:px-6");
  });

  it("applies narrow, wide, and full variants", () => {
    const { rerender, container } = render(
      <HqPageContainer variant="narrow">
        <span />
      </HqPageContainer>,
    );
    expect((container.firstElementChild as HTMLElement).className).toContain("max-w-[640px]");
    rerender(
      <HqPageContainer variant="wide">
        <span />
      </HqPageContainer>,
    );
    expect((container.firstElementChild as HTMLElement).className).toContain("max-w-[1200px]");
    rerender(
      <HqPageContainer variant="full">
        <span />
      </HqPageContainer>,
    );
    expect((container.firstElementChild as HTMLElement).className).toContain("max-w-full");
  });

  it("merges className", () => {
    const { container } = render(
      <HqPageContainer className="flex gap-4 py-8">
        <span />
      </HqPageContainer>,
    );
    expect((container.firstElementChild as HTMLElement).className).toContain("flex gap-4 py-8");
  });
});
