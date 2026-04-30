"use client";

import { useEffect, useMemo, useState } from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { MessageSquarePlus, Receipt, Workflow, Shield } from "lucide-react";

import { buildNavGroups, type NavItem } from "@/lib/admin-navigation";

type PaletteNavRow = Pick<NavItem, "href" | "label" | "icon">;

const EXTRA_NAV: PaletteNavRow[] = [
  { href: "/admin/architecture?tab=flows", label: "Workflows", icon: Workflow },
  { href: "/admin/infrastructure?tab=secrets", label: "Secrets", icon: Shield },
];

const QUICK: PaletteNavRow[] = [
  {
    href: "/admin/brain/conversations?compose=1",
    label: "Compose conversation",
    icon: MessageSquarePlus,
  },
  { href: "/admin/expenses?log=1", label: "Log expense", icon: Receipt },
];

function pathHint(href: string): string {
  try {
    const u = new URL(href, "http://local");
    return u.pathname + u.search;
  } catch {
    return href;
  }
}

export const STUDIO_COMMAND_PALETTE_OPEN_EVENT = "studio:open-command-palette";

export function openCommandPalette() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(STUDIO_COMMAND_PALETTE_OPEN_EVENT));
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

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
    const onOpen = () => setOpen(true);
    window.addEventListener(STUDIO_COMMAND_PALETTE_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(STUDIO_COMMAND_PALETTE_OPEN_EVENT, onOpen);
  }, []);

  const navigationRows = useMemo(() => {
    const groups = buildNavGroups(null, null);
    const flat: PaletteNavRow[] = [];
    for (const g of groups) {
      for (const item of g.items) {
        flat.push({ href: item.href, label: item.label, icon: item.icon });
      }
    }
    return [...flat, ...EXTRA_NAV];
  }, []);

  function go(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      overlayClassName="fixed inset-0 z-50 bg-black/40 backdrop-blur-xl transition-opacity duration-150 data-[state=closed]:opacity-0 data-[state=open]:opacity-100"
      contentClassName="fixed left-1/2 top-1/2 z-50 max-h-[min(80vh,560px)] w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border border-zinc-700/50 bg-zinc-900/95 p-0 shadow-2xl backdrop-blur-xl transition-all duration-150 data-[state=closed]:scale-95 data-[state=closed]:opacity-0 data-[state=open]:scale-100 data-[state=open]:opacity-100"
    >
      <h2 id="studio-command-palette-title" className="sr-only">
        Command palette
      </h2>
      <Command className="flex h-full max-h-[min(80vh,560px)] flex-col" aria-labelledby="studio-command-palette-title">
        <Command.Input
          placeholder="Search Studio..."
          className="w-full border-b border-zinc-700/50 bg-transparent px-4 py-3 text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
        />
        <Command.List className="max-h-[min(60vh,480px)] overflow-y-auto overscroll-contain p-2">
          <Command.Empty className="py-8 text-center text-sm text-zinc-500">No results.</Command.Empty>

          <Command.Group
            heading="Navigation"
            className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-zinc-500"
          >
            {navigationRows.map((row) => (
              <Command.Item
                key={row.href}
                value={`${row.label} ${row.href}`}
                onSelect={() => go(row.href)}
                className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-300 outline-none hover:bg-zinc-800 data-[selected=true]:bg-zinc-800 aria-selected:bg-zinc-800"
              >
                <row.icon className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
                <span className="min-w-0 flex-1 truncate">{row.label}</span>
                <span className="shrink-0 font-mono text-[10px] text-zinc-500 tabular-nums">
                  {pathHint(row.href)}
                </span>
              </Command.Item>
            ))}
          </Command.Group>

          <Command.Group
            heading="Quick Actions"
            className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-zinc-500"
          >
            {QUICK.map((row) => (
              <Command.Item
                key={row.href}
                value={`${row.label} ${row.href}`}
                onSelect={() => go(row.href)}
                className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-300 outline-none hover:bg-zinc-800 data-[selected=true]:bg-zinc-800 aria-selected:bg-zinc-800"
              >
                <row.icon className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
                <span className="min-w-0 flex-1 truncate">{row.label}</span>
                <span className="shrink-0 font-mono text-[10px] text-zinc-500 tabular-nums">
                  {pathHint(row.href)}
                </span>
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>
      </Command>
    </Command.Dialog>
  );
}
