"use client";

import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  cn,
} from "@paperwork-labs/ui";
import { Check, ChevronDown } from "lucide-react";

export type ProductBreadcrumbSwitcherProps = {
  currentSlug: string;
  options: { slug: string; label: string }[];
  className?: string;
};

export function ProductBreadcrumbSwitcher({
  currentSlug,
  options,
  className,
}: ProductBreadcrumbSwitcherProps) {
  const router = useRouter();
  const current = options.find((o) => o.slug === currentSlug);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-1 py-0.5 font-medium text-zinc-200 outline-none ring-offset-zinc-950 focus-visible:ring-2 focus-visible:ring-zinc-500",
          className,
        )}
        aria-label={`Current product: ${current?.label ?? currentSlug}. Switch product.`}
      >
        {current?.label ?? currentSlug}
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-zinc-500" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-[12rem]">
        {options.map((o) => (
          <DropdownMenuItem
            key={o.slug}
            className="cursor-pointer gap-2"
            onSelect={() => {
              router.push(`/admin/products/${o.slug}`);
            }}
          >
            <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
              <span className="truncate">{o.label}</span>
              {o.slug === currentSlug ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" aria-hidden />
              ) : null}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
