"use client";

import Link from "next/link";
import { Check, ChevronDown } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  cn,
} from "@paperwork-labs/ui";

export type ProductPlanCrumb = {
  slug: string;
  label: string;
};

type ProductPlanBreadcrumbProps = {
  currentSlug: string;
  products: ProductPlanCrumb[];
};

export function ProductPlanBreadcrumb({ currentSlug, products }: ProductPlanBreadcrumbProps) {
  const current = products.find((p) => p.slug === currentSlug);
  const label = current?.label ?? currentSlug;

  return (
    <nav aria-label="Breadcrumb" className="text-xs text-zinc-400">
      <ol className="flex flex-wrap items-center gap-1.5">
        <li>
          <Link href="/admin" className="text-zinc-300 motion-safe:transition-colors hover:text-zinc-100">
            Admin
          </Link>
        </li>
        <span className="text-zinc-600" aria-hidden>
          /
        </span>
        <li>
          <Link
            href="/admin/products"
            className="text-zinc-300 motion-safe:transition-colors hover:text-zinc-100"
          >
            Products
          </Link>
        </li>
        <span className="text-zinc-600" aria-hidden>
          /
        </span>
        <li className="flex items-center gap-1.5">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                data-testid="product-plan-product-switcher"
                aria-label={`Current product: ${label}. Open menu to switch product plans.`}
                className={cn(
                  "inline-flex max-w-[min(100%,16rem)] items-center gap-1 rounded-md px-1 py-0.5 text-left font-medium text-zinc-200",
                  "motion-safe:transition-colors hover:bg-zinc-800/80 hover:text-zinc-50",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--status-info)]",
                )}
              >
                <span className="truncate">{label}</span>
                <ChevronDown className="h-3.5 w-3.5 shrink-0 text-zinc-400" aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              className="studio-overlay-focus-scope max-h-[min(24rem,70vh)] overflow-y-auto border-zinc-700 bg-zinc-900 text-zinc-100"
            >
              <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
                Switch product
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-zinc-800" />
              {products.map((p) => {
                const selected = p.slug === currentSlug;
                return (
                  <DropdownMenuItem key={p.slug} asChild className="cursor-pointer p-0 focus:bg-transparent">
                    <Link
                      href={`/admin/products/${p.slug}/plan`}
                      data-testid={`product-plan-switch-${p.slug}`}
                      className={cn(
                        "flex w-full items-center gap-2 px-2 py-2.5 text-sm focus:bg-zinc-800 focus:text-zinc-50",
                        selected && "bg-zinc-800/80",
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate font-medium">{p.label}</span>
                      {selected ? (
                        <Check className="h-4 w-4 shrink-0 text-emerald-400" aria-hidden />
                      ) : null}
                    </Link>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </li>
      </ol>
    </nav>
  );
}
