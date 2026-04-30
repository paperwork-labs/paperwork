import type { ReactNode } from "react";
import Link from "next/link";

export type BreadcrumbItem =
  | { label: string; href: string }
  | { label: string; href?: undefined };

export type HqPageHeaderProps = {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: ReactNode;
  breadcrumbs?: BreadcrumbItem[];
};

/**
 * Top-of-page chrome for Studio HQ admin routes — title, optional eyebrow,
 * breadcrumbs, and trailing actions.
 */
export function HqPageHeader({
  title,
  subtitle,
  eyebrow,
  actions,
  breadcrumbs,
}: HqPageHeaderProps) {
  return (
    <header className="space-y-3">
      {breadcrumbs?.length ? (
        <nav aria-label="Breadcrumb" className="text-xs text-zinc-500">
          <ol className="flex flex-wrap items-center gap-1.5">
            {breadcrumbs.map((crumb, i) => (
              <li key={`${crumb.label}-${i}`} className="flex items-center gap-1.5">
                {i > 0 ? <span className="text-zinc-600" aria-hidden>/</span> : null}
                {crumb.href ? (
                  <Link
                    href={crumb.href}
                    className="text-zinc-400 transition hover:text-zinc-200"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="font-medium text-zinc-300">{crumb.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          {eyebrow ? (
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="text-lg font-semibold tracking-tight text-zinc-100 md:text-xl lg:text-2xl">
            {title}
          </h1>
          {subtitle ? <p className="max-w-3xl text-sm text-zinc-400">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
