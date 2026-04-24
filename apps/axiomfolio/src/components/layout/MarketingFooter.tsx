import * as React from 'react';
import { Link } from 'react-router-dom';

import { cn } from '@/lib/utils';

const SUPPORT_EMAIL = 'support@axiomfolio.com';

export interface MarketingFooterProps {
  className?: string;
}

/**
 * Shared footer for public marketing pages.
 */
export function MarketingFooter({ className }: MarketingFooterProps) {
  return (
    <footer
      className={cn(
        'border-t border-border bg-muted/30 py-6 text-center text-sm text-muted-foreground',
        className,
      )}
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-2 gap-y-1 px-4 sm:px-6">
        <span className="text-muted-foreground">© 2026 AxiomFolio</span>
        <span aria-hidden className="text-muted-foreground/80">
          ·
        </span>
        <Link to="/why-free" className="underline-offset-4 hover:text-foreground hover:underline">
          Why free
        </Link>
        <span aria-hidden className="text-muted-foreground/80">
          ·
        </span>
        <Link to="/pricing" className="underline-offset-4 hover:text-foreground hover:underline">
          Pricing
        </Link>
        <span aria-hidden className="text-muted-foreground/80">
          ·
        </span>
        <Link to="/terms" className="underline-offset-4 hover:text-foreground hover:underline">
          Terms
        </Link>
        <span aria-hidden className="text-muted-foreground/80">
          ·
        </span>
        <Link to="/privacy" className="underline-offset-4 hover:text-foreground hover:underline">
          Privacy
        </Link>
        <span aria-hidden className="text-muted-foreground/80">
          ·
        </span>
        <Link to="/status" className="underline-offset-4 hover:text-foreground hover:underline">
          Status
        </Link>
        <span aria-hidden className="text-muted-foreground/80">
          ·
        </span>
        <a
          className="font-mono underline-offset-4 hover:text-foreground hover:underline"
          href={`mailto:${SUPPORT_EMAIL}`}
        >
          {SUPPORT_EMAIL}
        </a>
      </div>
    </footer>
  );
}
