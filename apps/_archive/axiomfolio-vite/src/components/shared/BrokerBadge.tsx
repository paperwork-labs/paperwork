import React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const BROKER_LABELS: Record<string, string> = {
  ibkr: 'IBKR',
  schwab: 'Schwab',
  tastytrade: 'Tastytrade',
  fidelity: 'Fidelity',
  robinhood: 'Robinhood',
  etrade: 'E*TRADE',
  tradier: 'Tradier',
  tradier_sandbox: 'Tradier (sandbox)',
  coinbase: 'Coinbase',
};

const BROKER_TONE: Record<string, string> = {
  ibkr: 'border-sky-500/40 text-sky-700 dark:text-sky-300 bg-sky-500/10',
  schwab: 'border-blue-500/40 text-blue-700 dark:text-blue-300 bg-blue-500/10',
  tastytrade: 'border-amber-500/40 text-amber-700 dark:text-amber-300 bg-amber-500/10',
  fidelity: 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300 bg-emerald-500/10',
  robinhood: 'border-lime-500/40 text-lime-700 dark:text-lime-300 bg-lime-500/10',
  etrade: 'border-violet-500/40 text-violet-700 dark:text-violet-300 bg-violet-500/10',
  tradier: 'border-teal-500/40 text-teal-700 dark:text-teal-300 bg-teal-500/10',
};

export interface BrokerBadgeProps {
  broker?: string | null;
  accountNumber?: string | null;
  className?: string;
}

/**
 * Compact per-broker badge for multi-broker lists (positions, orders,
 * trades). Keeps the broker provenance visible so the founder/user can
 * immediately tell which position came from which connected broker
 * without having to hover over an account number.
 */
export const BrokerBadge: React.FC<BrokerBadgeProps> = ({ broker, accountNumber, className }) => {
  const key = (broker ?? '').toLowerCase();
  if (!key) return null;
  const label = BROKER_LABELS[key] ?? key.toUpperCase();
  const tone = BROKER_TONE[key] ?? 'border-muted-foreground/30 text-muted-foreground';
  return (
    <Badge
      variant="outline"
      className={cn('font-mono text-[10px] uppercase tracking-wide', tone, className)}
      title={accountNumber ? `${label} · ${accountNumber}` : label}
    >
      {label}
    </Badge>
  );
};

export default BrokerBadge;
