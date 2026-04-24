import * as React from "react";
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";

import { useFocusTrap, useHotkey, useRovingTabIndex } from "../useKeyboard";

describe("useHotkey", () => {
  it("fires when the matching key is pressed at the window level", () => {
    const handler = vi.fn();
    renderHook(() => useHotkey("k", handler, { meta: true }));
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("ignores the keypress when modifiers don't match", () => {
    const handler = vi.fn();
    renderHook(() => useHotkey("k", handler, { meta: true }));
    fireEvent.keyDown(window, { key: "k" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("skips when the focused element is a text input by default", () => {
    const handler = vi.fn();
    renderHook(() => useHotkey("k", handler));
    const input = document.createElement("input");
    input.type = "text";
    document.body.appendChild(input);
    input.focus();
    fireEvent.keyDown(input, { key: "k", target: input });
    expect(handler).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("fires inside text inputs when preventInTextInputs is false", () => {
    const handler = vi.fn();
    renderHook(() =>
      useHotkey("k", handler, { preventInTextInputs: false }),
    );
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    fireEvent.keyDown(input, { key: "k" });
    expect(handler).toHaveBeenCalledTimes(1);
    document.body.removeChild(input);
  });

  it("respects the enabled flag", () => {
    const handler = vi.fn();
    renderHook(() => useHotkey("a", handler, { enabled: false }));
    fireEvent.keyDown(window, { key: "a" });
    expect(handler).not.toHaveBeenCalled();
  });
});

function RovingList({ count = 3 }: { count?: number }) {
  const { activeIndex, getItemProps } = useRovingTabIndex(count);
  return (
    <div data-testid="list">
      {Array.from({ length: count }).map((_, i) => {
        const props = getItemProps(i);
        return (
          <button
            key={i}
            data-testid={`item-${i}`}
            data-active={i === activeIndex}
            tabIndex={props.tabIndex}
            ref={props.ref as (el: HTMLButtonElement | null) => void}
            onKeyDown={props.onKeyDown}
            type="button"
          >
            Item {i}
          </button>
        );
      })}
    </div>
  );
}

describe("useRovingTabIndex", () => {
  it("only the active item gets tabIndex=0", () => {
    render(<RovingList count={3} />);
    expect(screen.getByTestId("item-0").tabIndex).toBe(0);
    expect(screen.getByTestId("item-1").tabIndex).toBe(-1);
    expect(screen.getByTestId("item-2").tabIndex).toBe(-1);
  });

  it("ArrowRight advances and ArrowLeft retreats", () => {
    render(<RovingList count={3} />);
    const first = screen.getByTestId("item-0");
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(screen.getByTestId("item-1").tabIndex).toBe(0);
    expect(document.activeElement).toBe(screen.getByTestId("item-1"));
    fireEvent.keyDown(screen.getByTestId("item-1"), { key: "ArrowLeft" });
    expect(screen.getByTestId("item-0").tabIndex).toBe(0);
  });

  it("loops at the boundaries by default", () => {
    render(<RovingList count={3} />);
    fireEvent.keyDown(screen.getByTestId("item-0"), { key: "ArrowLeft" });
    expect(screen.getByTestId("item-2").tabIndex).toBe(0);
  });

  it("Home/End jump to first/last", () => {
    render(<RovingList count={3} />);
    fireEvent.keyDown(screen.getByTestId("item-0"), { key: "End" });
    expect(screen.getByTestId("item-2").tabIndex).toBe(0);
    fireEvent.keyDown(screen.getByTestId("item-2"), { key: "Home" });
    expect(screen.getByTestId("item-0").tabIndex).toBe(0);
  });

  it("clamps activeIndex when itemCount shrinks below the current value (regression for C1)", () => {
    function Shrinker() {
      const [count, setCount] = React.useState(4);
      const { activeIndex, getItemProps } = useRovingTabIndex(count);
      return (
        <div>
          <span data-testid="active">{activeIndex}</span>
          <button data-testid="shrink" onClick={() => setCount(2)}>
            Shrink
          </button>
          {Array.from({ length: count }).map((_, i) => {
            const props = getItemProps(i);
            return (
              <button
                key={i}
                data-testid={`it-${i}`}
                tabIndex={props.tabIndex}
                ref={props.ref as (el: HTMLButtonElement | null) => void}
                onKeyDown={props.onKeyDown}
                type="button"
              >
                {i}
              </button>
            );
          })}
        </div>
      );
    }
    render(<Shrinker />);
    // Move active to index 3 (last of 4).
    const it0 = screen.getByTestId("it-0");
    it0.focus();
    fireEvent.keyDown(it0, { key: "End" });
    expect(screen.getByTestId("active").textContent).toBe("3");

    // Shrink to 2 items. Without the clamp, activeIndex stays at 3 and
    // no rendered button has tabIndex=0 — the group becomes
    // unreachable by Tab.
    act(() => {
      screen.getByTestId("shrink").click();
    });

    expect(screen.getByTestId("active").textContent).toBe("1");
    expect(screen.getByTestId("it-0").tabIndex).toBe(-1);
    expect(screen.getByTestId("it-1").tabIndex).toBe(0);
  });
});

function TrapHarness({ enabled }: { enabled: boolean }) {
  const ref = useFocusTrap<HTMLDivElement>(enabled);
  return (
    <>
      <button data-testid="outside-before">Outside before</button>
      <div ref={ref} data-testid="trap">
        <button data-testid="inner-1">Inner 1</button>
        <button data-testid="inner-2">Inner 2</button>
      </div>
      <button data-testid="outside-after">Outside after</button>
    </>
  );
}

describe("useFocusTrap", () => {
  it("focuses first focusable on mount and wraps Tab inside the container", () => {
    render(<TrapHarness enabled />);
    expect(document.activeElement).toBe(screen.getByTestId("inner-1"));
    fireEvent.keyDown(screen.getByTestId("trap"), { key: "Tab" });
    // Focus moves naturally in the harness; simulate landing on last and pressing Tab.
    screen.getByTestId("inner-2").focus();
    fireEvent.keyDown(screen.getByTestId("trap"), { key: "Tab" });
    expect(document.activeElement).toBe(screen.getByTestId("inner-1"));
  });

  it("Shift+Tab from first wraps to last", () => {
    render(<TrapHarness enabled />);
    expect(document.activeElement).toBe(screen.getByTestId("inner-1"));
    fireEvent.keyDown(screen.getByTestId("trap"), {
      key: "Tab",
      shiftKey: true,
    });
    expect(document.activeElement).toBe(screen.getByTestId("inner-2"));
  });

  it("restores the container's prior tabindex when there are no focusables (regression for C2)", () => {
    function EmptyTrap({ enabled }: { enabled: boolean }) {
      const ref = useFocusTrap<HTMLDivElement>(enabled);
      return (
        <div ref={ref} data-testid="empty-trap">
          {/* No focusable children */}
        </div>
      );
    }

    // Case 1: container had NO tabindex originally → cleanup must remove it.
    const { rerender, unmount } = render(<EmptyTrap enabled={true} />);
    const trap1 = screen.getByTestId("empty-trap");
    expect(trap1.getAttribute("tabindex")).toBe("-1");
    rerender(<EmptyTrap enabled={false} />);
    expect(trap1.hasAttribute("tabindex")).toBe(false);
    unmount();

    // Case 2: container had a pre-existing tabindex → cleanup must restore.
    function PreExistingTabindex({ enabled }: { enabled: boolean }) {
      const ref = useFocusTrap<HTMLDivElement>(enabled);
      return (
        <div
          ref={ref}
          data-testid="pre"
          tabIndex={5}
        />
      );
    }
    const { rerender: rerender2 } = render(
      <PreExistingTabindex enabled={true} />,
    );
    const pre = screen.getByTestId("pre");
    // While trapped (no focusables), the hook overrides to -1.
    expect(pre.getAttribute("tabindex")).toBe("-1");
    rerender2(<PreExistingTabindex enabled={false} />);
    // After teardown, the original tabindex must be restored verbatim.
    expect(pre.getAttribute("tabindex")).toBe("5");
  });

  it("restores focus to the previously-focused element on disable", async () => {
    function Harness() {
      const [open, setOpen] = React.useState(false);
      const ref = useFocusTrap<HTMLDivElement>(open);
      return (
        <>
          <button data-testid="opener" onClick={() => setOpen(true)}>
            Open
          </button>
          {open && (
            <div ref={ref} data-testid="trap">
              <button data-testid="closer" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
          )}
        </>
      );
    }
    render(<Harness />);
    const opener = screen.getByTestId("opener");
    opener.focus();
    expect(document.activeElement).toBe(opener);
    act(() => {
      opener.click();
    });
    expect(document.activeElement).toBe(screen.getByTestId("closer"));
    act(() => {
      screen.getByTestId("closer").click();
    });
    expect(document.activeElement).toBe(opener);
  });
});
