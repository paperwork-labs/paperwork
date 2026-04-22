import * as React from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import AppLogo from '@/components/ui/AppLogo';

export interface MarketingHeaderProps {
  className?: string;
}

/**
 * Shared chrome for public marketing pages (Why free, Pricing).
 */
export function MarketingHeader({ className }: MarketingHeaderProps) {
  return (
    <header
      className={cn(
        'border-b border-border bg-card/60 backdrop-blur',
        className
      )}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <Link
          to="/"
          aria-label="AxiomFolio home"
          className={cn(
            'flex items-center gap-2.5 rounded-md',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background'
          )}
        >
          <AppLogo size={40} />
          <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
            AxiomFolio
          </span>
        </Link>
        <nav
          className="flex flex-wrap items-center justify-end gap-x-4 gap-y-2 text-sm"
          aria-label="Marketing"
        >
          <Link
            to="/why-free"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Why free
          </Link>
          <Link
            to="/pricing"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Pricing
          </Link>
          <Link
            to="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
          <Link
            to="/register"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Register
          </Link>
        </nav>
      </div>
    </header>
  );
}
