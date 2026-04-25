import type { ConnectionsBrokerHealthStatus } from '@/services/connectionsHealth';
import { cn } from '@/lib/utils';

/** Status dot colors — centralized so tiles and health strip stay consistent. */
export function connectionStatusDotClass(status: ConnectionsBrokerHealthStatus | 'not_connected'): string {
  switch (status) {
    case 'connected':
      return 'bg-emerald-500';
    case 'stale':
      return 'bg-amber-500';
    case 'error':
      return 'bg-destructive';
    case 'disconnected':
    case 'not_connected':
    default:
      return 'bg-muted-foreground/40';
  }
}

export function connectionStatusLabel(args: {
  status: ConnectionsBrokerHealthStatus;
  hasAccounts: boolean;
  relativeLastSync: string | null;
  oauthExpired?: boolean;
}): string {
  const { status, hasAccounts, relativeLastSync, oauthExpired } = args;
  if (!hasAccounts) return 'Not connected';
  if (oauthExpired || status === 'stale') return 'Token expired · reconnect';
  if (status === 'error') return 'Error';
  if (relativeLastSync) return `Connected · last sync ${relativeLastSync}`;
  return 'Connected';
}

export function healthBannerClass(kind: 'stale' | 'error'): string {
  return cn(
    'rounded-md border px-3 py-2 text-sm',
    kind === 'error'
      ? 'border-destructive/50 bg-destructive/10 text-destructive'
      : 'border-amber-500/50 bg-amber-500/10 text-amber-900 dark:text-amber-100',
  );
}
