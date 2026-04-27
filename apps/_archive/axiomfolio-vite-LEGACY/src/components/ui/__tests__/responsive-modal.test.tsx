import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  ResponsiveModal,
  ResponsiveModalContent,
  ResponsiveModalDescription,
  ResponsiveModalHeader,
  ResponsiveModalTitle,
} from "../responsive-modal";

type MockMatchMedia = (query: string) => MediaQueryList;

function setMatchMedia(matchesFor: (query: string) => boolean) {
  const impl: MockMatchMedia = (query) => {
    return {
      matches: matchesFor(query),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    } as unknown as MediaQueryList;
  };
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn(impl),
  });
}

function harness(extraProps?: { showDragHandle?: boolean }) {
  return (
    <ResponsiveModal open onOpenChange={() => {}}>
      <ResponsiveModalContent {...extraProps}>
        <ResponsiveModalHeader>
          <ResponsiveModalTitle>Test sheet title</ResponsiveModalTitle>
          <ResponsiveModalDescription>
            Test sheet description
          </ResponsiveModalDescription>
        </ResponsiveModalHeader>
        <p>Body content</p>
      </ResponsiveModalContent>
    </ResponsiveModal>
  );
}

describe("ResponsiveModal", () => {
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    // start each test from a clean matchMedia
    setMatchMedia(() => false);
  });

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      configurable: true,
      value: originalMatchMedia,
    });
  });

  it("renders content, title, and description regardless of variant (desktop)", () => {
    setMatchMedia((q) => q.includes("min-width: 768px"));
    render(harness());
    expect(screen.getByText("Test sheet title")).toBeInTheDocument();
    expect(screen.getByText("Test sheet description")).toBeInTheDocument();
    expect(screen.getByText("Body content")).toBeInTheDocument();
  });

  it("renders content on mobile via Vaul drawer with a drag handle", () => {
    // matchMedia returns false for >=768 -> mobile branch
    setMatchMedia(() => false);
    render(harness());
    expect(screen.getByText("Test sheet title")).toBeInTheDocument();
    expect(screen.getByText("Body content")).toBeInTheDocument();
    // Portals render to document.body, not the test container.
    const content = document.querySelector(
      '[data-slot="responsive-modal-content"]',
    );
    expect(content).not.toBeNull();
    // Drag handle is the decorative pill at the top of the sheet.
    const handle = content?.querySelector(
      'div[aria-hidden="true"].rounded-full',
    );
    expect(handle).not.toBeNull();
  });

  it("omits the drag handle when showDragHandle is false on mobile", () => {
    setMatchMedia(() => false);
    render(harness({ showDragHandle: false }));
    const content = document.querySelector(
      '[data-slot="responsive-modal-content"]',
    );
    expect(content).not.toBeNull();
    expect(
      content?.querySelector('div[aria-hidden="true"].rounded-full'),
    ).toBeNull();
  });

  it("desktop variant uses Radix Dialog content (no drag handle present)", () => {
    setMatchMedia((q) => q.includes("min-width: 768px"));
    render(harness());
    const content = document.querySelector(
      '[data-slot="responsive-modal-content"]',
    );
    expect(content).not.toBeNull();
    // Desktop content has no decorative drag handle pill.
    expect(
      content?.querySelector('div[aria-hidden="true"].rounded-full'),
    ).toBeNull();
  });
});
