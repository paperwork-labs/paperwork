import React from 'react';
import { cn } from '@/lib/utils';
import AppLogo from '../ui/AppLogo';

type Props = React.ComponentProps<'div'> & { children: React.ReactNode };

/**
 * Auth shell: full-viewport center, dark gradient background,
 * prominent brand mark + product name above the card slot.
 */
export default function AuthLayout({ children, className, style, ...props }: Props) {
  return (
    <div
      {...props}
      className={cn(
        'relative flex min-h-screen flex-col items-center justify-center px-4 py-10 text-white md:px-8 md:py-14',
        className
      )}
      style={{
        background:
          'radial-gradient(1200px 600px at 20% 10%, rgba(29,78,216,0.18), transparent 55%), radial-gradient(900px 500px at 85% 25%, rgba(245,158,11,0.10), transparent 55%), #0F172A',
        ...style,
      }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'radial-gradient(900px 500px at 50% 20%, rgba(255,255,255,0.06), transparent 60%)',
        }}
      />
      <div className="relative w-full max-w-[420px] md:max-w-[440px]">
        <div className="mb-6 flex items-center justify-center gap-3.5">
          <AppLogo size={72} />
          <span className="text-xl font-semibold tracking-tight text-white">AxiomFolio</span>
        </div>
        {children}
      </div>
    </div>
  );
}
