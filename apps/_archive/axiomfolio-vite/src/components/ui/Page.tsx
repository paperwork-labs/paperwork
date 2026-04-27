import React from 'react';
import { cn } from '@/lib/utils';

export type PageContainerWidth = 'narrow' | 'default' | 'wide' | 'full';

const PAGE_CONTAINER_MAX: Record<Exclude<PageContainerWidth, 'full'>, string> = {
  /** UX audit G-11 — 640px narrow column. */
  narrow: 'max-w-[640px]',
  /** UX audit G-11: one canonical reading width for in-app and marketing copy. */
  default: 'max-w-[960px]',
  wide: 'max-w-[1200px]',
};

export function PageContainer({
  width = 'default',
  className,
  children,
  ...rest
}: {
  width?: PageContainerWidth;
  className?: string;
  children: React.ReactNode;
} & React.ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'mx-auto w-full px-4 md:px-6',
        width !== 'full' && PAGE_CONTAINER_MAX[width as Exclude<PageContainerWidth, 'full'>],
        width === 'full' && 'max-w-none',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface PageProps extends React.ComponentProps<'div'> {
  children: React.ReactNode;
  fullWidth?: boolean;
}

export function Page({ children, className, fullWidth, ...props }: PageProps) {
  return (
    <div
      className={cn(
        'mx-auto w-full px-4 py-6 md:px-6 md:py-8',
        !fullWidth && 'max-w-[1200px]',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export interface PageHeaderProps extends React.ComponentProps<'div'> {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  rightContent?: React.ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  actions,
  rightContent,
  className,
  ...props
}: PageHeaderProps) {
  return (
    <div className="mb-6">
      <div
        className={cn('flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between', className)}
        {...props}
      >
        <div className="min-w-0">
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
            {title}
          </h1>
          {subtitle ? <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p> : null}
        </div>
        {rightContent ? <div className="shrink-0">{rightContent}</div> : null}
      </div>
      {actions ? <div className="mt-2">{actions}</div> : null}
    </div>
  );
}

export default PageHeader;
