"use client";

import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Boxes,
  CircleDot,
  Kanban,
  LayoutDashboard,
  ListTree,
  MessageSquare,
  RefreshCw,
  Search,
  Shield,
  Target,
  Users,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { STUDIO_KEYBOARD_HELP_OPEN_EVENT } from "@/hooks/use-keyboard-shortcuts";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@paperwork-labs/ui";

export const STUDIO_COMMAND_PALETTE_OPEN_EVENT = "studio:open-command-palette";

export function openCommandPalette(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(STUDIO_COMMAND_PALETTE_OPEN_EVENT));
}

function fuzzyMatch(query: string, text: string): boolean {
  if (!query) return true;
  let qi = 0;
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) qi++;
  }
  return qi === q.length;
}

type PaletteCategory = "Navigate" | "Actions";

type PaletteCommand = {
  id: string;
  category: PaletteCategory;
  label: string;
  hint?: string;
  searchText: string;
  icon: LucideIcon;
  run: () => void;
};

const DIALOG_OVERLAY_Z = "z-[80]";
const DIALOG_CONTENT_Z = "z-[90]";

export function KeyboardShortcutsHelpDialog() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener(STUDIO_KEYBOARD_HELP_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(STUDIO_KEYBOARD_HELP_OPEN_EVENT, onOpen);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        hideClose
        overlayClassName={DIALOG_OVERLAY_Z}
        className={`${DIALOG_CONTENT_Z} max-w-md gap-4 border-zinc-800 bg-zinc-900 p-6 text-zinc-100 shadow-2xl sm:rounded-xl`}
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <DialogTitle className="text-base font-semibold text-zinc-100">Keyboard shortcuts</DialogTitle>
        <DialogDescription className="sr-only">
          Studio admin navigation and command palette shortcuts
        </DialogDescription>
        <div className="max-h-[min(70vh,420px)] space-y-4 overflow-y-auto text-sm">
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
              Command palette
            </p>
            <ul className="space-y-1.5 text-zinc-300">
              <li className="flex justify-between gap-4">
                <span>Open / close</span>
                <kbd className="shrink-0 rounded border border-zinc-700 bg-zinc-800 px-1.5 font-mono text-[10px] text-zinc-400">
                  ⌘K
                </kbd>
              </li>
            </ul>
          </div>
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
              Go to (press G, then key within 500ms)
            </p>
            <ul className="space-y-1.5 text-zinc-300">
              {[
                ["Overview", "G then O"],
                ["People", "G then P"],
                ["Epics", "G then E"],
                ["Products", "G then R"],
                ["Infrastructure", "G then I"],
                ["Conversations", "G then C"],
                ["Docs", "G then D"],
                ["Circles", "G then T"],
              ].map(([label, combo]) => (
                <li key={label} className="flex justify-between gap-4">
                  <span>{label}</span>
                  <span className="shrink-0 font-mono text-[10px] text-zinc-400">{combo}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">Help</p>
            <ul className="space-y-1.5 text-zinc-300">
              <li className="flex justify-between gap-4">
                <span>Show this panel</span>
                <kbd className="shrink-0 rounded border border-zinc-700 bg-zinc-800 px-1.5 font-mono text-[10px] text-zinc-400">
                  ?
                </kbd>
              </li>
            </ul>
          </div>
        </div>
        <p className="text-xs text-zinc-500">Shortcuts are disabled while typing in inputs. Press Escape to close.</p>
      </DialogContent>
    </Dialog>
  );
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const activeItemRef = useRef<HTMLButtonElement>(null);

  const commands = useMemo<PaletteCommand[]>(() => {
    const nav = (
      href: string,
      label: string,
      hint: string,
      icon: LucideIcon,
      extraSearch = "",
    ): PaletteCommand => ({
      id: `nav-${href}`,
      category: "Navigate",
      label,
      hint,
      searchText: `${label} ${href} ${hint} ${extraSearch}`,
      icon,
      run: () => {
        setOpen(false);
        router.push(href);
      },
    });

    return [
      nav("/admin", "Overview", "G O", LayoutDashboard),
      nav("/admin/people", "People", "G P", Users),
      nav("/admin/workstreams", "Epics", "G E", Kanban, "workstreams"),
      nav("/admin/products", "Products", "G R", Boxes),
      nav("/admin/infrastructure", "Infrastructure", "G I", Shield),
      nav("/admin/conversations", "Conversations", "G C", MessageSquare),
      nav("/admin/docs", "Docs", "G D", BookOpen),
      nav("/admin/circles", "Circles", "G T", CircleDot),
      {
        id: "action-new-goal",
        category: "Actions",
        label: "New Goal",
        hint: "N G",
        searchText: "new goal create okr N G",
        icon: Target,
        run: () => {
          setOpen(false);
          router.push("/admin/goals");
        },
      },
      {
        id: "action-new-epic",
        category: "Actions",
        label: "New Epic",
        hint: "N E",
        searchText: "new epic workstream N E",
        icon: ListTree,
        run: () => {
          setOpen(false);
          router.push("/admin/workstreams");
        },
      },
      {
        id: "action-refresh",
        category: "Actions",
        label: "Refresh",
        hint: "R",
        searchText: "refresh reload R",
        icon: RefreshCw,
        run: () => {
          setOpen(false);
          router.refresh();
        },
      },
    ];
  }, [router]);

  const filtered = useMemo(() => {
    const q = query.trim();
    return commands.filter((c) => fuzzyMatch(q, c.searchText));
  }, [commands, query]);

  const rows = useMemo(() => {
    const navigate = filtered.filter((c) => c.category === "Navigate");
    const actions = filtered.filter((c) => c.category === "Actions");
    return [...navigate, ...actions];
  }, [filtered]);

  const sections = useMemo(() => {
    const navigate = filtered.filter((c) => c.category === "Navigate");
    const actions = filtered.filter((c) => c.category === "Actions");
    const out: { label: PaletteCategory; items: PaletteCommand[] }[] = [];
    if (navigate.length) out.push({ label: "Navigate", items: navigate });
    if (actions.length) out.push({ label: "Actions", items: actions });
    return out;
  }, [filtered]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onPaletteOpen = () => setOpen(true);
    window.addEventListener(STUDIO_COMMAND_PALETTE_OPEN_EVENT, onPaletteOpen);
    return () => window.removeEventListener(STUDIO_COMMAND_PALETTE_OPEN_EVENT, onPaletteOpen);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setSelectedIndex(0);
  }, [open]);

  useEffect(() => {
    setSelectedIndex((i) => {
      if (rows.length === 0) return 0;
      return Math.min(i, rows.length - 1);
    });
  }, [rows.length, query]);

  useLayoutEffect(() => {
    if (!open || !activeItemRef.current || !listRef.current) return;
    activeItemRef.current.scrollIntoView({ block: "nearest" });
  }, [open, selectedIndex, rows]);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  const onPaletteKeyDown = useCallback(
    (e: ReactKeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => (rows.length === 0 ? 0 : (i + 1) % rows.length));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) =>
          rows.length === 0 ? 0 : (i - 1 + rows.length) % rows.length,
        );
        return;
      }
      if (e.key === "Enter") {
        const cmd = rows[selectedIndex];
        if (cmd) {
          e.preventDefault();
          cmd.run();
        }
      }
    },
    [rows, selectedIndex],
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        hideClose
        overlayClassName={`${DIALOG_OVERLAY_Z} bg-black/70`}
        className={`${DIALOG_CONTENT_Z} max-h-[min(85vh,560px)] max-w-xl gap-0 overflow-hidden border border-zinc-800 bg-zinc-900 p-0 text-zinc-100 shadow-2xl sm:rounded-xl`}
        onCloseAutoFocus={(e) => e.preventDefault()}
        onKeyDown={onPaletteKeyDown}
      >
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">
          Search admin destinations and actions. Use arrow keys and Enter.
        </DialogDescription>

        <div className="flex items-center gap-2 border-b border-zinc-800 px-3 py-2.5">
          <Search className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
          <input
            ref={inputRef}
            type="search"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            placeholder="Search commands…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
          />
        </div>

        <div
          ref={listRef}
          className="max-h-[min(60vh,480px)] overflow-y-auto overscroll-contain p-2"
          role="listbox"
          aria-label="Commands"
        >
          {rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-zinc-500">No matching commands.</p>
          ) : (
            sections.map((section, sectionIdx) => (
              <div key={section.label}>
                <p
                  className={`px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-500 ${
                    sectionIdx === 0 ? "pt-0" : "pt-2"
                  }`}
                >
                  {section.label}
                </p>
                {section.items.map((cmd) => {
                  const idx = rows.findIndex((r) => r.id === cmd.id);
                  const active = idx === selectedIndex;
                  return (
                    <button
                      key={cmd.id}
                      type="button"
                      role="option"
                      aria-selected={active}
                      ref={active ? activeItemRef : undefined}
                      data-active={active ? "true" : undefined}
                      onClick={() => cmd.run()}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left text-sm outline-none motion-safe:transition-colors ${
                        active ? "bg-zinc-800 text-zinc-50" : "text-zinc-300 hover:bg-zinc-800/60"
                      }`}
                    >
                      <cmd.icon className="h-4 w-4 shrink-0 text-zinc-400" aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{cmd.label}</span>
                      {cmd.hint ? (
                        <span className="shrink-0 font-mono text-[10px] tabular-nums text-zinc-500">
                          {cmd.hint.replace(/\s+/g, " ")}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <div className="border-t border-zinc-800 px-3 py-2 text-[10px] text-zinc-500">
          <span className="font-medium text-zinc-400">Enter</span> run ·{" "}
          <span className="font-medium text-zinc-400">Esc</span> close ·{" "}
          <span className="font-medium text-zinc-400">↑↓</span> move
        </div>
      </DialogContent>
    </Dialog>
  );
}
