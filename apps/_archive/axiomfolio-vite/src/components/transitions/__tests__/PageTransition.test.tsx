import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("framer-motion", async () => {
  const actual = await vi.importActual<typeof import("framer-motion")>(
    "framer-motion",
  );
  return {
    ...actual,
    useReducedMotion: vi.fn(() => false),
  };
});

import { useReducedMotion } from "framer-motion";
import {
  PageTransition,
  SharedLayoutGroup,
} from "../PageTransition";

const useReducedMotionMock = vi.mocked(useReducedMotion);

afterEach(() => {
  useReducedMotionMock.mockReturnValue(false);
});

describe("PageTransition", () => {
  it("renders its children inside a motion wrapper", () => {
    render(
      <PageTransition>
        <p>hello world</p>
      </PageTransition>,
    );
    expect(screen.getByTestId("page-transition")).toBeInTheDocument();
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("forwards a custom className", () => {
    render(
      <PageTransition className="page-x">
        <span>x</span>
      </PageTransition>,
    );
    expect(screen.getByTestId("page-transition").className).toMatch(/page-x/);
  });

  it("still mounts children when the user prefers reduced motion", () => {
    useReducedMotionMock.mockReturnValue(true);
    render(
      <PageTransition>
        <p>reduced</p>
      </PageTransition>,
    );
    expect(screen.getByText("reduced")).toBeInTheDocument();
    expect(screen.getByTestId("page-transition")).toBeInTheDocument();
  });
});

describe("SharedLayoutGroup", () => {
  it("renders its children inside the layout group wrapper", () => {
    render(
      <SharedLayoutGroup id="test-group">
        <span>child</span>
      </SharedLayoutGroup>,
    );
    expect(screen.getByText("child")).toBeInTheDocument();
  });
});
