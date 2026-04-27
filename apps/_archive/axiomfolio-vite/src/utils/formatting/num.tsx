import * as React from 'react';

import { cn } from '@/lib/utils';

/**
 * Wraps numeric content with tabular lining figures so columns align in tables
 * and stat cards. Prefer this (or `className="tabular-nums"`) for any
 * user-facing $ / % / count that should not jitter horizontally.
 */
export const Num: React.FC<React.HTMLAttributes<HTMLSpanElement>> = ({ className, ...rest }) => (
  <span className={cn('tabular-nums', className)} {...rest} />
);
