/**
 * Keyboard navigation primitives.
 *
 * - `useHotkey` registers a single key+modifier handler, optionally skipping
 *   text inputs so chrome shortcuts don't fight typing.
 * - `useRovingTabIndex` implements the WAI-ARIA roving-tabindex pattern for
 *   horizontal/vertical/grid lists (radio groups, toolbar buttons, tab lists).
 * - `useFocusTrap` confines tabbing to a container and restores focus on
 *   teardown — the basic building block for modals/dialogs.
 *
 * All three hooks are framework-agnostic (just React + DOM), have zero
 * external dependencies, and clean up after themselves on unmount.
 */
import * as React from "react";

type ModifierKey = "meta" | "ctrl" | "shift" | "alt";

export interface UseHotkeyOptions {
  meta?: boolean;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  /** Disable the listener without unmounting the hook. */
  enabled?: boolean;
  /**
   * When the focused element is a text input (`input`, `textarea`,
   * `[contenteditable]`), skip the handler so the user's typing isn't
   * intercepted. Defaults to `true`.
   */
  preventInTextInputs?: boolean;
}

const TEXT_INPUT_TAGS = new Set(["INPUT", "TEXTAREA"]);

function isTextInput(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (TEXT_INPUT_TAGS.has(target.tagName)) {
    if (target instanceof HTMLInputElement) {
      const nonText = new Set([
        "button",
        "submit",
        "checkbox",
        "radio",
        "range",
        "color",
        "file",
        "hidden",
      ]);
      return !nonText.has(target.type);
    }
    return true;
  }
  return target.isContentEditable;
}

function modifiersMatch(e: KeyboardEvent, opts: UseHotkeyOptions): boolean {
  const want = (k: ModifierKey) => Boolean(opts[k]);
  return (
    e.metaKey === want("meta") &&
    e.ctrlKey === want("ctrl") &&
    e.shiftKey === want("shift") &&
    e.altKey === want("alt")
  );
}

export function useHotkey(
  key: string,
  handler: (e: KeyboardEvent) => void,
  opts: UseHotkeyOptions = {},
): void {
  const handlerRef = React.useRef(handler);
  React.useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  const {
    enabled = true,
    preventInTextInputs = true,
    meta = false,
    ctrl = false,
    shift = false,
    alt = false,
  } = opts;

  React.useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== key.toLowerCase()) return;
      if (!modifiersMatch(e, { meta, ctrl, shift, alt })) return;
      if (preventInTextInputs && isTextInput(e.target)) return;
      handlerRef.current(e);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [key, enabled, preventInTextInputs, meta, ctrl, shift, alt]);
}

export type RovingOrientation = "horizontal" | "vertical" | "both";

export interface UseRovingTabIndexOptions {
  orientation?: RovingOrientation;
  /** Wrap focus from last back to first (and vice versa). Default `true`. */
  loop?: boolean;
}

export interface RovingItemProps {
  tabIndex: number;
  onKeyDown: (e: React.KeyboardEvent) => void;
  ref: (el: HTMLElement | null) => void;
}

export interface UseRovingTabIndexReturn {
  activeIndex: number;
  setActiveIndex: (i: number) => void;
  getItemProps: (index: number) => RovingItemProps;
}

export function useRovingTabIndex(
  itemCount: number,
  options: UseRovingTabIndexOptions = {},
): UseRovingTabIndexReturn {
  const { orientation = "horizontal", loop = true } = options;
  const [activeIndex, setActiveIndexState] = React.useState(0);
  const itemRefs = React.useRef<Array<HTMLElement | null>>([]);
  const shouldFocusRef = React.useRef(false);

  React.useEffect(() => {
    itemRefs.current.length = itemCount;
    // Clamp `activeIndex` when the collection shrinks so we never end up in
    // a state where no item has tabIndex=0 (which breaks Tab navigation
    // into the group). We deliberately do NOT focus on a clamp: this is a
    // structural correction, not a user-driven move, so `shouldFocusRef`
    // is left untouched (defaulting to false).
    setActiveIndexState((prev) => {
      if (itemCount === 0) return 0;
      if (prev > itemCount - 1) return itemCount - 1;
      if (prev < 0) return 0;
      return prev;
    });
  }, [itemCount]);

  React.useEffect(() => {
    if (!shouldFocusRef.current) return;
    shouldFocusRef.current = false;
    const node = itemRefs.current[activeIndex];
    node?.focus();
  }, [activeIndex]);

  const setActiveIndex = React.useCallback((i: number) => {
    setActiveIndexState(i);
  }, []);

  const moveTo = React.useCallback(
    (i: number) => {
      shouldFocusRef.current = true;
      setActiveIndexState(i);
    },
    [],
  );

  const getItemProps = React.useCallback(
    (index: number): RovingItemProps => ({
      tabIndex: index === activeIndex ? 0 : -1,
      ref: (el: HTMLElement | null) => {
        itemRefs.current[index] = el;
      },
      onKeyDown: (e: React.KeyboardEvent) => {
        if (itemCount === 0) return;
        const horiz = orientation === "horizontal" || orientation === "both";
        const vert = orientation === "vertical" || orientation === "both";
        let next = index;
        if (horiz && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
          next = e.key === "ArrowRight" ? index + 1 : index - 1;
        } else if (vert && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
          next = e.key === "ArrowDown" ? index + 1 : index - 1;
        } else if (e.key === "Home") {
          next = 0;
        } else if (e.key === "End") {
          next = itemCount - 1;
        } else {
          return;
        }
        if (next < 0) next = loop ? itemCount - 1 : 0;
        if (next >= itemCount) next = loop ? 0 : itemCount - 1;
        if (next === index) return;
        e.preventDefault();
        moveTo(next);
      },
    }),
    [activeIndex, itemCount, loop, moveTo, orientation],
  );

  return { activeIndex, setActiveIndex, getItemProps };
}

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "iframe",
  "object",
  "embed",
  "[tabindex]:not([tabindex='-1'])",
  "[contenteditable='true']",
].join(",");

function getFocusable(container: HTMLElement): HTMLElement[] {
  const nodes = Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  );
  return nodes.filter((el) => {
    if (el.hasAttribute("disabled")) return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    return true;
  });
}

export function useFocusTrap<T extends HTMLElement = HTMLElement>(
  enabled: boolean,
): React.RefObject<T | null> {
  const containerRef = React.useRef<T | null>(null);
  const previousFocusRef = React.useRef<HTMLElement | null>(null);

  React.useEffect(() => {
    if (!enabled) return;
    const container = containerRef.current;
    if (!container) return;

    previousFocusRef.current = document.activeElement as HTMLElement | null;

    // Capture the original `tabindex` so we can restore it precisely on
    // cleanup. `null` means the attribute was absent — we'll remove ours
    // rather than leaving stale state behind.
    const hadTabindexAttr = container.hasAttribute("tabindex");
    const originalTabindex = hadTabindexAttr
      ? container.getAttribute("tabindex")
      : null;
    let didSetTabindex = false;

    const focusables = getFocusable(container);
    if (focusables.length > 0) {
      focusables[0].focus();
    } else {
      container.setAttribute("tabindex", "-1");
      didSetTabindex = true;
      container.focus();
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const items = getFocusable(container);
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (active === first || !container.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last || !container.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    container.addEventListener("keydown", onKeyDown);
    return () => {
      container.removeEventListener("keydown", onKeyDown);
      // Restore tabindex precisely: only touch the attribute if we set it.
      if (didSetTabindex) {
        if (hadTabindexAttr && originalTabindex !== null) {
          container.setAttribute("tabindex", originalTabindex);
        } else {
          container.removeAttribute("tabindex");
        }
      }
      const prev = previousFocusRef.current;
      if (prev && document.contains(prev)) {
        prev.focus();
      }
    };
  }, [enabled]);

  return containerRef;
}
