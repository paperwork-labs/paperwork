import React from "react";
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  page: number; // 1-based
  pageSize: number;
  total: number;
  pageSizeOptions?: number[];
  onPageChange: (page: number) => void; // 1-based
  onPageSizeChange: (pageSize: number) => void;
};

const defaultPageSizes = [10, 25, 50, 100];

const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, n));

const rangeLabel = (page: number, pageSize: number, total: number) => {
  if (total <= 0) return "0–0 of 0";
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);
  return `${start}–${end} of ${total}`;
};

const buildPageItems = (page: number, totalPages: number) => {
  const p = clamp(page, 1, totalPages);
  const visible = new Set<number>(
    [1, totalPages, p, p - 1, p + 1, p - 2, p + 2].filter((x) => x >= 1 && x <= totalPages)
  );
  const sorted = Array.from(visible).sort((a, b) => a - b);

  const out: Array<number | "ellipsis"> = [];
  for (let i = 0; i < sorted.length; i++) {
    const cur = sorted[i];
    const prev = sorted[i - 1];
    if (i > 0 && prev !== undefined && cur - prev > 1) out.push("ellipsis");
    out.push(cur);
  }
  const finalOut: Array<number | "ellipsis"> = [];
  const seenNum = new Set<number>();
  for (const it of out) {
    if (it === "ellipsis") {
      if (finalOut[finalOut.length - 1] !== "ellipsis") finalOut.push("ellipsis");
      continue;
    }
    if (seenNum.has(it)) continue;
    seenNum.add(it);
    finalOut.push(it);
  }
  return finalOut;
};

export default function Pagination({
  page,
  pageSize,
  total,
  pageSizeOptions = defaultPageSizes,
  onPageChange,
  onPageSizeChange,
}: Props) {
  const totalPages = Math.max(1, Math.ceil((total || 0) / pageSize));
  const safePage = clamp(page, 1, totalPages);
  const items = buildPageItems(safePage, totalPages);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft' && safePage > 1) {
      e.preventDefault();
      onPageChange(safePage - 1);
    } else if (e.key === 'ArrowRight' && safePage < totalPages) {
      e.preventDefault();
      onPageChange(safePage + 1);
    }
  };

  return (
    <nav
      aria-label={`Pagination, page ${safePage} of ${totalPages}`}
      className="flex w-full flex-wrap items-center justify-between gap-3"
      onKeyDown={handleKeyDown}
    >
      <p className="text-xs text-muted-foreground">{rangeLabel(safePage, pageSize, total || 0)}</p>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button
          type="button"
          aria-label="Previous page"
          size="icon-sm"
          variant="outline"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
        >
          <ChevronLeft className="size-4" />
        </Button>

        <div className="flex flex-wrap items-center gap-1" role="list" aria-label="Page numbers">
          {items.map((it, idx) =>
            it === "ellipsis" ? (
              <span
                key={`e-${idx}`}
                className="flex items-center px-2 text-muted-foreground"
                aria-hidden
              >
                <MoreHorizontal className="size-4" />
              </span>
            ) : (
              <Button
                key={it}
                type="button"
                size="sm"
                variant={it === safePage ? "default" : "outline"}
                className="min-w-9 px-2"
                onClick={() => onPageChange(it)}
                aria-label={`Page ${it} of ${totalPages}`}
                aria-current={it === safePage ? "page" : undefined}
              >
                {it}
              </Button>
            )
          )}
        </div>

        <Button
          type="button"
          aria-label="Next page"
          size="icon-sm"
          variant="outline"
          disabled={safePage >= totalPages}
          onClick={() => onPageChange(safePage + 1)}
        >
          <ChevronRight className="size-4" />
        </Button>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button type="button" size="sm" variant="outline" aria-label="Page size">
              {pageSize} / page
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={4}
              className={cn(
                "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 min-w-[10rem] overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md data-[state=closed]:animate-out data-[state=open]:animate-in"
              )}
            >
              {pageSizeOptions.map((opt) => (
                <DropdownMenu.Item
                  key={opt}
                  className={cn(
                    "relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none",
                    "focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                  )}
                  onSelect={() => onPageSizeChange(opt)}
                >
                  {opt} per page
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </nav>
  );
}
