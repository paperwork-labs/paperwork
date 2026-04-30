"use client";

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { Menu, X } from 'lucide-react';

import AppLogo from '@/components/ui/AppLogo';
import { Button } from '@/components/ui/button';
import { useIsDesktop } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/utils';

const navLinkClass = (
  { isActive }: { isActive: boolean },
  stacked: boolean,
) =>
  cn(
    'text-sm font-medium transition-colors',
    stacked && 'block py-2',
    isActive
      ? 'text-foreground underline decoration-primary underline-offset-4'
      : 'text-muted-foreground hover:text-foreground',
  );

const marketingNav = [
  { to: '/why-free', label: 'Why free' },
  { to: '/pricing', label: 'Pricing' },
] as const;

function MarketingNavLinks({
  onNavigate,
  stacked = false,
}: {
  onNavigate?: () => void;
  stacked?: boolean;
}) {
  const pathname = usePathname();
  return (
    <>
      {marketingNav.map(({ to, label }) => {
        const isActive = pathname === to;
        return (
          <Link
            key={to}
            href={to}
            className={navLinkClass({ isActive }, stacked)}
            onClick={onNavigate}
          >
            {label}
          </Link>
        );
      })}
      <Button asChild size="sm" variant="default" className={cn(stacked && 'w-full')}>
        <Link href="/sign-in" onClick={onNavigate}>
          Sign in
        </Link>
      </Button>
      <Button asChild size="sm" variant="outline" className={cn(stacked && 'w-full')}>
        <Link href="/sign-up" onClick={onNavigate}>
          Register
        </Link>
      </Button>
    </>
  );
}

export interface MarketingHeaderProps {
  className?: string;
}

/**
 * Shared chrome for public marketing pages (Why free, Pricing).
 * Desktop: inline nav. Sub-`md`: menu button opens a left sheet (same interaction
 * model as `DashboardLayout`’s mobile nav — Radix Dialog slide-in) so primary
 * actions stay reachable without horizontal overflow.
 */
export function MarketingHeader({ className }: MarketingHeaderProps) {
  const isDesktop = useIsDesktop();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  return (
    <header
      className={cn('border-b border-border bg-card/60 backdrop-blur', className)}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <Link
          href="/"
          aria-label="AxiomFolio home"
          className={cn(
            'flex min-w-0 items-center gap-2.5 rounded-md',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          )}
        >
          <AppLogo size={40} />
          <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
            AxiomFolio
          </span>
        </Link>

        {isDesktop ? (
          <nav
            className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2"
            aria-label="Marketing"
          >
            <MarketingNavLinks />
          </nav>
        ) : (
          <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
            <Dialog.Trigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="shrink-0 text-foreground"
                aria-label="Open marketing menu"
                aria-expanded={mobileOpen}
                aria-controls="marketing-header-mobile-nav"
              >
                <Menu className="size-5" aria-hidden />
              </Button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
              <Dialog.Content
                id="marketing-header-mobile-nav"
                className="fixed top-0 right-0 z-50 flex h-screen w-[min(100vw,320px)] max-w-[90vw] flex-col border-l border-border bg-background p-0 shadow-lg outline-none data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right-2 data-[state=open]:animate-in data-[state=open]:slide-in-from-right-2"
                onPointerDownOutside={() => setMobileOpen(false)}
                onEscapeKeyDown={() => setMobileOpen(false)}
              >
                <div className="flex items-center justify-between border-b border-border px-4 py-3">
                  <Dialog.Title className="font-heading text-base font-semibold text-foreground">
                    Menu
                  </Dialog.Title>
                  <Dialog.Close asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0"
                      aria-label="Close menu"
                    >
                      <X className="size-5" aria-hidden />
                    </Button>
                  </Dialog.Close>
                </div>
                <Dialog.Description className="sr-only">
                  Marketing links, sign in, and register
                </Dialog.Description>
                <nav
                  className="flex flex-col gap-3 p-4"
                  aria-label="Marketing"
                >
                  <MarketingNavLinks
                    stacked
                    onNavigate={() => setMobileOpen(false)}
                  />
                </nav>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        )}
      </div>
    </header>
  );
}
