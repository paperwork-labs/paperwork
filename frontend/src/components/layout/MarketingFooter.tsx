import * as React from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

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
        className
      )}
    >
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-center gap-2 px-4 sm:px-6">
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
          <Link to="/why-free" className="underline-offset-4 hover:text-foreground hover:underline">
            Why free
          </Link>
          <span className="text-muted-foreground" aria-hidden>
            ·
          </span>
          <Link to="/pricing" className="underline-offset-4 hover:text-foreground hover:underline">
            Pricing
          </Link>
          <span className="text-muted-foreground" aria-hidden>
            ·
          </span>
          <span>Terms (coming soon)</span>
          <span className="text-muted-foreground" aria-hidden>
            ·
          </span>
          <span>Privacy (coming soon)</span>
        </div>
      </div>
    </footer>
  );
}
