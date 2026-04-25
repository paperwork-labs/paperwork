import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import hotToast from 'react-hot-toast';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { useAuth } from '../../context/AuthContext';
import { isPlatformAdminRole } from '../../utils/userRole';
import { useCircuitBreakerStatus, useResetCircuitBreakerKillSwitch } from '../../hooks/useCircuitBreaker';
import type { CircuitBreakerStatus } from '../../types/circuitBreaker';

function tierAlertConfig(tier: number): {
  variant: 'default' | 'destructive';
  className: string;
  title: string;
  Icon: React.FC<{ className?: string }>;
} {
  if (tier >= 3) {
    return {
      variant: 'destructive',
      className: 'border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-300',
      title: 'Trading Halted',
      Icon: AlertCircle,
    };
  }
  if (tier === 2) {
    return {
      variant: 'default',
      className: 'border-orange-500/50 bg-orange-500/10 text-orange-700 dark:text-orange-300',
      title: 'Entries Blocked',
      Icon: AlertTriangle,
    };
  }
  if (tier === 1) {
    return {
      variant: 'default',
      className: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-700 dark:text-yellow-300',
      title: 'Circuit Warning',
      Icon: AlertTriangle,
    };
  }
  return {
    variant: 'default',
    className: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300',
    title: 'Normal',
    Icon: CheckCircle2,
  };
}

function KillSwitchBadge({ active }: { active: boolean }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        'font-normal',
        active
          ? 'border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-300'
          : 'border-border bg-muted/50 text-muted-foreground'
      )}
    >
      Kill switch {active ? 'ON' : 'off'}
    </Badge>
  );
}

function BannerBody({
  data,
  isAdmin,
  onReset,
  resetPending,
}: {
  data: CircuitBreakerStatus;
  isAdmin: boolean;
  onReset: () => void;
  resetPending: boolean;
}) {
  const { variant, className, title, Icon } = tierAlertConfig(data.tier);
  const isSubtle = data.tier === 0 && !data.kill_switch_active;

  return (
    <Alert variant={variant} className={cn('rounded-md', className)}>
      <Icon className="size-4" />
      <AlertTitle
        className={cn(
          'flex flex-wrap items-center justify-between gap-3',
          isSubtle ? 'text-sm' : 'text-base'
        )}
      >
        <span>{title}</span>
        {isAdmin && (
          <Button
            size="sm"
            variant="outline"
            disabled={!data.kill_switch_active || resetPending}
            onClick={onReset}
            aria-label="Reset kill switch"
            className="h-7 text-xs"
          >
            {resetPending && <Loader2 className="mr-1 size-3 animate-spin" />}
            Reset kill switch
          </Button>
        )}
      </AlertTitle>
      <AlertDescription className="mt-1 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span>
            Daily loss:{' '}
            <span className="font-semibold">{data.daily_pnl_pct.toFixed(2)}%</span>
          </span>
          <KillSwitchBadge active={data.kill_switch_active} />
          {data.trip_reason && (
            <span className="text-muted-foreground">{data.trip_reason}</span>
          )}
        </div>
        {data.reason && data.tier > 0 && (
          <p className="mt-1 text-xs opacity-90">{data.reason}</p>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function CircuitBreakerBanner() {
  const { user } = useAuth();
  const isAdmin = isPlatformAdminRole(user?.role);
  const { data, isPending, isError } = useCircuitBreakerStatus();
  const resetMutation = useResetCircuitBreakerKillSwitch();

  const handleReset = () => {
    resetMutation.mutate(undefined, {
      onSuccess: () => {
        hotToast.success('Kill switch cleared');
      },
      onError: () => {
        hotToast.error('Could not reset kill switch');
      },
    });
  };

  if (!isPending && (isError || !data)) {
    return null;
  }

  if (isPending) {
    return (
      <div className="flex items-center gap-2 px-1 py-2 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        <span className="text-sm">Loading circuit breaker…</span>
      </div>
    );
  }

  return (
    <BannerBody
      data={data}
      isAdmin={isAdmin}
      onReset={handleReset}
      resetPending={resetMutation.isPending}
    />
  );
}
