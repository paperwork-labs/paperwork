import React from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { RefreshCw, Rocket, AlertTriangle } from 'lucide-react';
import useDeployHealth from '../../hooks/useDeployHealth';
import type {
  DeployEvent,
  DeployServiceSummary,
} from '../../types/adminHealth';
import { formatDateTime } from '../../utils/format';
import { useUserPreferences } from '../../hooks/useUserPreferences';

/**
 * G28 deploy-health tile for the admin dashboard (D120).
 *
 * Distinguishes the four states explicitly per `no-silent-fallback.mdc`:
 * loading | error | empty (no services configured) | data.
 *
 * Green/yellow/red indicate service-by-service status. A red card surfaces
 * the midnight-merge-storm pattern (3+ consecutive failures or 4+ failures
 * in 24h) before the pipeline serves stale snapshots.
 */

function statusClass(status: string): string {
  switch (status) {
    case 'green':
      return 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]';
    case 'yellow':
      return 'border-transparent bg-[rgb(var(--status-warning)/0.12)] text-[rgb(var(--status-warning)/1)]';
    case 'red':
      return 'border-transparent bg-destructive/10 text-destructive';
    default:
      return 'border-transparent bg-muted text-muted-foreground';
  }
}

function eventStatusClass(status: string, isPollError: boolean): string {
  if (isPollError) return 'text-destructive';
  if (status === 'live') return 'text-[rgb(var(--status-success)/1)]';
  if (status === 'build_failed' || status === 'update_failed' || status === 'canceled' || status === 'pre_deploy_failed') {
    return 'text-destructive';
  }
  if (status === 'deactivated') return 'text-muted-foreground';
  return 'text-[rgb(var(--status-warning)/1)]';
}

const ServiceRow: React.FC<{ service: DeployServiceSummary; timezone?: string }> = ({
  service,
  timezone,
}) => (
  <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-muted/30 px-3 py-2">
    <div className="flex min-w-0 flex-col">
      <div className="flex items-center gap-2">
        <span className="truncate text-sm font-medium">
          {service.service_slug || service.service_id}
        </span>
        <Badge
          variant="outline"
          className={cn('font-medium uppercase', statusClass(service.status))}
        >
          {service.status.toUpperCase()}
        </Badge>
        {service.in_flight && (
          <Badge variant="outline" className="text-xs">
            in-flight
          </Badge>
        )}
      </div>
      <p className="truncate text-xs text-muted-foreground">{service.reason}</p>
    </div>
    <div className="flex shrink-0 flex-col items-end text-xs text-muted-foreground">
      <span>
        Last:{' '}
        <span className={eventStatusClass(service.last_status || '', false)}>
          {service.last_status || '—'}
        </span>
        {service.last_deploy_sha ? ` · ${service.last_deploy_sha.slice(0, 8)}` : ''}
      </span>
      <span>
        {service.last_deploy_at
          ? formatDateTime(service.last_deploy_at, timezone)
          : '—'}
      </span>
      <span>
        {service.failures_24h > 0 ? `${service.failures_24h} failed` : 'no failures'} · 24h
        {service.consecutive_failures > 0
          ? ` · ${service.consecutive_failures} in a row`
          : ''}
      </span>
    </div>
  </div>
);

const EventRow: React.FC<{ event: DeployEvent; timezone?: string }> = ({
  event,
  timezone,
}) => (
  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 px-1 py-1 text-xs last:border-0">
    <div className="flex min-w-0 items-center gap-2">
      <span
        className={cn('font-mono', eventStatusClass(event.status, event.is_poll_error))}
      >
        {event.status}
      </span>
      <span className="truncate text-muted-foreground">
        {event.service_slug || event.service_id}
      </span>
      {event.commit_sha && (
        <span className="font-mono text-muted-foreground">
          {event.commit_sha.slice(0, 8)}
        </span>
      )}
    </div>
    <div className="flex shrink-0 items-center gap-2 text-muted-foreground">
      {event.is_poll_error && (
        <span className="flex items-center gap-1 text-destructive">
          <AlertTriangle className="h-3 w-3" /> poll error
        </span>
      )}
      <span>{formatDateTime(event.render_created_at, timezone)}</span>
    </div>
  </div>
);

const DeployHealthCard: React.FC = () => {
  const { data, isLoading, isError, error, refresh, poll, polling } = useDeployHealth();
  const { timezone } = useUserPreferences();

  const body = (() => {
    if (isLoading) {
      return (
        <p className="text-xs text-muted-foreground">Loading deploy telemetry…</p>
      );
    }
    if (isError) {
      const message =
        (error as { message?: string } | null)?.message ??
        'Failed to load deploy telemetry';
      return (
        <div className="flex items-center gap-2 text-xs text-destructive">
          <AlertTriangle className="h-4 w-4" />
          <span>{message}</span>
        </div>
      );
    }
    if (!data || data.services_configured === 0) {
      return (
        <p className="text-xs text-muted-foreground">
          No Render services configured. Set <code>DEPLOY_HEALTH_SERVICE_IDS</code>{' '}
          (comma-separated) to start collecting deploy telemetry.
        </p>
      );
    }
    const services = data.services ?? [];
    const events = data.events ?? [];
    return (
      <>
        <div className="flex flex-col gap-2">
          {services.map((svc) => (
            <ServiceRow
              key={svc.service_id}
              service={svc}
              timezone={timezone}
            />
          ))}
        </div>
        {events.length > 0 && (
          <div className="mt-3">
            <p className="mb-1 text-xs font-semibold text-muted-foreground">
              Recent deploy events
            </p>
            <div className="rounded-md border border-border bg-muted/20 px-2 py-1">
              {events.slice(0, 8).map((ev) => (
                <EventRow key={ev.id} event={ev} timezone={timezone} />
              ))}
            </div>
          </div>
        )}
      </>
    );
  })();

  const compositeStatus = data?.status ?? (isError ? 'red' : 'yellow');

  return (
    <Card className="gap-0 py-0 shadow-xs ring-1 ring-border lg:col-span-2">
      <div className="flex flex-col gap-3 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Rocket className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-semibold">Deploy Health</span>
            <Badge
              variant="outline"
              className={cn('font-medium uppercase', statusClass(compositeStatus))}
            >
              {compositeStatus.toUpperCase()}
            </Badge>
            {data && (
              <span className="text-xs text-muted-foreground">
                {data.services_configured} service
                {data.services_configured === 1 ? '' : 's'} · {data.failures_24h_total} failed / 24h
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void refresh()}
              disabled={isLoading}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void poll()}
              disabled={polling || !data || data.services_configured === 0}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', polling && 'animate-spin')} />
              Poll now
            </Button>
          </div>
        </div>
        {data?.reason && !isError && data.services_configured > 0 && (
          <p className="text-xs text-muted-foreground">{data.reason}</p>
        )}
        {body}
      </div>
    </Card>
  );
};

export default DeployHealthCard;
