import React from 'react';
import { cn } from '@/lib/utils';

export function Page({ children, className, ...props }: React.ComponentProps<'div'> & { children: React.ReactNode }) {
  return (
    <div
      className={cn('mx-auto w-full max-w-[1200px] px-4 py-6 md:px-6 md:py-8', className)}
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
