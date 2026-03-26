import React from 'react';
import { cn } from '@/lib/utils';

interface ToolbarProps {
  children: React.ReactNode;
  className?: string;
}

const Toolbar: React.FC<ToolbarProps> = ({ children, className }) => {
  return (
    <div
      className={cn(
        'rounded-md border border-border bg-muted/40 p-3 shadow-xs dark:bg-muted/20',
        className
      )}
    >
      <div className="flex flex-wrap items-center gap-4">{children}</div>
    </div>
  );
};

export default Toolbar;
