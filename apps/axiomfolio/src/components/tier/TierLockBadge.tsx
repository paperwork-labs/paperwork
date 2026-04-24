import React from 'react';
import { Lock } from 'lucide-react';

interface TierLockBadgeProps {
  label?: string;
}

export const TierLockBadge: React.FC<TierLockBadgeProps> = ({ label = 'Upgrade required' }) => {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground">
      <Lock aria-hidden className="size-3" />
      {label}
    </span>
  );
};

export default TierLockBadge;
