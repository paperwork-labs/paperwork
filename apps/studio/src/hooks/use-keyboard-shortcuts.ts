"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

const SEQUENCE_MS = 500;

const G_NAV: Record<string, string> = {
  o: "/admin",
  p: "/admin/people",
  e: "/admin/workstreams",
  r: "/admin/products",
  i: "/admin/infrastructure",
  c: "/admin/conversations",
  d: "/admin/docs",
  t: "/admin/circles",
};

export const STUDIO_KEYBOARD_HELP_OPEN_EVENT = "studio:open-keyboard-help";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

function hasOpenDialog(): boolean {
  return document.querySelectorAll('[role="dialog"][data-state="open"]').length > 0;
}

/**
 * Global admin shortcuts: G then letter (500ms window) for navigation, ? for help.
 * Skips when focus is in a field or when a dialog is already open. Does not handle Cmd/Ctrl+K.
 */
export function useKeyboardShortcuts(): void {
  const router = useRouter();
  const armedRef = useRef<{ timeoutId: ReturnType<typeof setTimeout> } | null>(null);

  useEffect(() => {
    const disarm = () => {
      const cur = armedRef.current;
      if (cur) {
        clearTimeout(cur.timeoutId);
        armedRef.current = null;
      }
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target)) return;
      if (hasOpenDialog()) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === "?") {
        e.preventDefault();
        disarm();
        window.dispatchEvent(new CustomEvent(STUDIO_KEYBOARD_HELP_OPEN_EVENT));
        return;
      }

      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;

      if (armedRef.current) {
        disarm();
        const path = G_NAV[key];
        if (path) {
          e.preventDefault();
          router.push(path);
        }
        return;
      }

      if (key === "g") {
        e.preventDefault();
        armedRef.current = {
          timeoutId: setTimeout(() => {
            armedRef.current = null;
          }, SEQUENCE_MS),
        };
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      disarm();
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [router]);
}
