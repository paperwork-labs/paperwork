import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ClipboardList, Info, ShieldAlert, Target } from 'lucide-react';

import api from '@/services/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

type ContractStatus =
  | 'ready'
  | 'chain_unavailable'
  | 'stock_only'
  | 'skipped_earnings';

type SizingStatus =
  | 'computed'
  | 'account_unknown'
  | 'inputs_missing'
  | 'regime_blocked';

type AlertLevel = 'info' | 'warning' | 'critical';

interface UnderlyingPayload {
  symbol: string;
  name: string | null;
  sector: string | null;
  stage_label: string | null;
  current_price: string | null;
  rs_mansfield_pct: string | null;
  perf_5d: string | null;
  td_buy_setup: number | null;
  td_sell_setup: number | null;
  next_earnings: string | null;
  days_to_earnings: number | null;
  atr_14: string | null;
  atrp_14: string | null;
  sma_21: string | null;
  volume_avg_20d: string | null;
}

interface RegimePayload {
  regime_state: string;
  composite_score: string | null;
  regime_multiplier: string;
  as_of_date: string | null;
}

interface ScorePayload {
  pick_quality_score: string;
  regime_multiplier: string;
  components: Record<
    string,
    { raw_score: string; weight: string; weighted_score: string; reason: string }
  >;
}

interface ContractPayload {
  contract_type: 'call_debit' | 'put_credit' | 'stock';
  occ_symbol: string;
  expiry: string;
  strike: string;
  bid: string;
  mid: string;
  ask: string;
  spread_pct: string;
  delta: string | null;
  open_interest: number | null;
  volume: number | null;
}

interface LimitTierPayload {
  tier: 'passive' | 'mid' | 'aggressive';
  price: string;
  logic: string;
  fill_likelihood: string;
}

interface SizingPayload {
  tier: 'T1' | 'T2' | 'T3' | null;
  contracts: number;
  shares: number;
  premium_dollars: string;
  premium_pct_of_account: string;
  full_position_dollars: string;
  capped_position_dollars: string;
  stage_cap: string;
  regime_multiplier: string;
  account_size: string;
  risk_budget: string;
}

interface StopsPayload {
  premium_stop: string | null;
  underlying_stop: string | null;
  underlying_stop_reason: string | null;
  calendar_stop: string | null;
  calendar_stop_reason: string | null;
}

interface AlertPayload {
  alert_type: string;
  level: AlertLevel;
  message: string;
}

interface TradeCardPayload {
  rank: number;
  candidate_id: number;
  generated_at: string;
  action: string;
  underlying: UnderlyingPayload;
  regime: RegimePayload;
  score: ScorePayload;
  contract_status: ContractStatus;
  contract: ContractPayload | null;
  limit_tiers: LimitTierPayload[];
  sizing_status: SizingStatus;
  sizing: SizingPayload | null;
  stops: StopsPayload;
  alerts: AlertPayload[];
  anti_thesis: string;
  notes: string[];
}

interface TradeCardErrorItem {
  candidate_id: number;
  symbol: string;
  error: string;
}

interface TradeCardsResponse {
  items: TradeCardPayload[];
  errors: TradeCardErrorItem[];
  total: number;
  limit: number;
  offset: number;
  user_id: number;
}

function fmtMoney(raw: string | null | undefined): string {
  if (raw == null) return '—';
  const n = Number(raw);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  });
}

function fmtNumber(raw: string | null | undefined, digits = 2): string {
  if (raw == null) return '—';
  const n = Number(raw);
  if (!Number.isFinite(n)) return '—';
  return n.toFixed(digits);
}

function stageBadgeClass(stage: string | null): string {
  if (!stage) return 'bg-muted text-muted-foreground';
  const s = stage.toUpperCase();
  if (s.startsWith('2')) return 'bg-primary/15 text-primary';
  if (s.startsWith('3') || s.startsWith('4')) return 'bg-destructive/15 text-destructive';
  return 'bg-muted text-muted-foreground';
}

function contractStatusLabel(status: ContractStatus): { label: string; tone: 'info' | 'warn' } {
  switch (status) {
    case 'ready':
      return { label: 'Contract ready', tone: 'info' };
    case 'stock_only':
      return { label: 'Stock only (no chain wired)', tone: 'warn' };
    case 'chain_unavailable':
      return { label: 'Chain unavailable', tone: 'warn' };
    case 'skipped_earnings':
      return { label: 'Chain skipped (earnings inside window)', tone: 'warn' };
    default:
      return { label: String(status), tone: 'warn' };
  }
}

function AlertIcon({ level }: { level: AlertLevel }) {
  switch (level) {
    case 'critical':
      return <ShieldAlert className="size-4" aria-hidden />;
    case 'warning':
      return <AlertTriangle className="size-4" aria-hidden />;
    default:
      return <Info className="size-4" aria-hidden />;
  }
}

function TradeCardRow({ card }: { card: TradeCardPayload }) {
  const u = card.underlying;
  const s = card.score;
  const r = card.regime;
  const contract = card.contract;
  const sizing = card.sizing;
  const stops = card.stops;
  const contractStatus = contractStatusLabel(card.contract_status);

  return (
    <Card data-testid={`trade-card-${card.candidate_id}`}>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 pb-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">#{card.rank}</span>
            <p className="font-mono text-xl font-semibold">{u.symbol}</p>
            <Badge className={cn('uppercase', stageBadgeClass(u.stage_label))}>
              Stage {u.stage_label ?? '—'}
            </Badge>
            {r.regime_state ? (
              <Badge variant="outline" className="uppercase">
                Regime {r.regime_state}
              </Badge>
            ) : null}
            <Badge className="bg-accent text-accent-foreground">{card.action}</Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {u.name ? `${u.name} · ` : ''}
            {u.sector ?? '—'}
            {u.current_price ? ` · ${fmtMoney(u.current_price)}` : ''}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase text-muted-foreground">Score</p>
          <p className="font-heading text-2xl font-semibold tabular-nums">
            {fmtNumber(s.pick_quality_score, 1)}
          </p>
          <p className="text-xs text-muted-foreground">
            Regime x{fmtNumber(r.regime_multiplier, 2)}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {card.notes.length > 0 ? (
          <Alert>
            <Info className="size-4" aria-hidden />
            <AlertTitle>Heads up</AlertTitle>
            <AlertDescription>
              {card.notes.map((n, i) => (
                <p key={`note-${i}`}>{n}</p>
              ))}
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <section aria-label="Underlying context" className="space-y-1">
            <p className="text-xs uppercase text-muted-foreground">Underlying</p>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
              <dt className="text-muted-foreground">RS Mansfield</dt>
              <dd className="tabular-nums">{fmtNumber(u.rs_mansfield_pct, 1)}</dd>
              <dt className="text-muted-foreground">5d perf</dt>
              <dd className="tabular-nums">{fmtNumber(u.perf_5d, 2)}%</dd>
              <dt className="text-muted-foreground">ATR(14) %</dt>
              <dd className="tabular-nums">{fmtNumber(u.atrp_14, 2)}</dd>
              <dt className="text-muted-foreground">TD Buy / Sell</dt>
              <dd className="tabular-nums">
                {u.td_buy_setup ?? '—'} / {u.td_sell_setup ?? '—'}
              </dd>
              <dt className="text-muted-foreground">Next earnings</dt>
              <dd className="tabular-nums">
                {u.next_earnings
                  ? `${new Date(u.next_earnings).toLocaleDateString()} (${u.days_to_earnings ?? '—'}d)`
                  : '—'}
              </dd>
              <dt className="text-muted-foreground">SMA21</dt>
              <dd className="tabular-nums">{fmtMoney(u.sma_21)}</dd>
            </dl>
          </section>

          <section aria-label="Contract and limits" className="space-y-1">
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase text-muted-foreground">Contract</p>
              <Badge
                variant={contractStatus.tone === 'info' ? 'secondary' : 'outline'}
                className={cn(
                  'text-xs',
                  contractStatus.tone === 'warn'
                    ? 'border-destructive/40 text-destructive'
                    : undefined,
                )}
              >
                {contractStatus.label}
              </Badge>
            </div>
            {contract ? (
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
                <dt className="text-muted-foreground">Symbol</dt>
                <dd className="font-mono">{contract.occ_symbol}</dd>
                <dt className="text-muted-foreground">Expiry / Strike</dt>
                <dd className="tabular-nums">
                  {new Date(contract.expiry).toLocaleDateString()} · {fmtMoney(contract.strike)}
                </dd>
                <dt className="text-muted-foreground">Bid / Mid / Ask</dt>
                <dd className="tabular-nums">
                  {fmtMoney(contract.bid)} / {fmtMoney(contract.mid)} / {fmtMoney(contract.ask)}
                </dd>
                <dt className="text-muted-foreground">Spread</dt>
                <dd className="tabular-nums">{fmtNumber(contract.spread_pct, 2)}%</dd>
                <dt className="text-muted-foreground">Delta / OI</dt>
                <dd className="tabular-nums">
                  {fmtNumber(contract.delta ?? null, 2)} · {contract.open_interest ?? '—'}
                </dd>
              </dl>
            ) : (
              <p className="text-muted-foreground">
                No live option contract selected. Limit tiers and stops below assume a stock fill
                and will adapt once the options-chain surface is wired.
              </p>
            )}
          </section>
        </div>

        <section aria-label="Limit tiers" className="space-y-1">
          <p className="text-xs uppercase text-muted-foreground">Limit tiers</p>
          {card.limit_tiers.length === 0 ? (
            <p className="text-muted-foreground">No price anchor available.</p>
          ) : (
            <ul className="grid gap-1 sm:grid-cols-3">
              {card.limit_tiers.map((t) => (
                <li
                  key={t.tier}
                  className="rounded-md border border-border bg-muted/40 p-2"
                  data-testid={`limit-${t.tier}`}
                >
                  <p className="text-xs uppercase text-muted-foreground">
                    {t.tier} · fill {t.fill_likelihood}
                  </p>
                  <p className="font-mono text-base tabular-nums">{fmtMoney(t.price)}</p>
                  <p className="text-xs text-muted-foreground">{t.logic}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Sizing" className="space-y-1">
          <p className="text-xs uppercase text-muted-foreground">Sizing</p>
          {card.sizing_status !== 'computed' ? (
            <p className="text-muted-foreground">
              {card.sizing_status === 'account_unknown'
                ? 'Connect a brokerage account to size this trade.'
                : card.sizing_status === 'regime_blocked'
                  ? 'Stage × regime cap = 0. Card is informational only.'
                  : 'Sizing inputs not yet available from the snapshot.'}
            </p>
          ) : sizing ? (
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-4">
              <dt className="text-muted-foreground">Tier</dt>
              <dd>{sizing.tier ?? '—'}</dd>
              <dt className="text-muted-foreground">Contracts</dt>
              <dd className="tabular-nums">{sizing.contracts}</dd>
              <dt className="text-muted-foreground">Shares (stock)</dt>
              <dd className="tabular-nums">{sizing.shares}</dd>
              <dt className="text-muted-foreground">Premium</dt>
              <dd className="tabular-nums">
                {fmtMoney(sizing.premium_dollars)} ({fmtNumber(sizing.premium_pct_of_account, 2)}%)
              </dd>
              <dt className="text-muted-foreground">Capped $</dt>
              <dd className="tabular-nums">{fmtMoney(sizing.capped_position_dollars)}</dd>
              <dt className="text-muted-foreground">Full $</dt>
              <dd className="tabular-nums">{fmtMoney(sizing.full_position_dollars)}</dd>
              <dt className="text-muted-foreground">Stage cap</dt>
              <dd className="tabular-nums">{fmtNumber(sizing.stage_cap, 2)}</dd>
              <dt className="text-muted-foreground">Account</dt>
              <dd className="tabular-nums">{fmtMoney(sizing.account_size)}</dd>
            </dl>
          ) : null}
        </section>

        <section aria-label="Stops" className="space-y-1">
          <p className="text-xs uppercase text-muted-foreground">Stops</p>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-3">
            <dt className="text-muted-foreground">Premium</dt>
            <dd className="tabular-nums">{fmtMoney(stops.premium_stop)}</dd>
            <dt className="text-muted-foreground">Underlying</dt>
            <dd className="tabular-nums">{fmtMoney(stops.underlying_stop)}</dd>
            <dt className="text-muted-foreground">Calendar</dt>
            <dd className="tabular-nums">{stops.calendar_stop ?? '—'}</dd>
          </dl>
          {stops.underlying_stop_reason ? (
            <p className="text-xs text-muted-foreground">{stops.underlying_stop_reason}</p>
          ) : null}
          {stops.calendar_stop_reason ? (
            <p className="text-xs text-muted-foreground">{stops.calendar_stop_reason}</p>
          ) : null}
        </section>

        {card.alerts.length > 0 ? (
          <section aria-label="Alerts" className="space-y-2">
            <p className="text-xs uppercase text-muted-foreground">Alerts</p>
            <ul className="space-y-1">
              {card.alerts.map((a, i) => (
                <li
                  key={`${a.alert_type}-${i}`}
                  className={cn(
                    'flex items-start gap-2 rounded-md border border-border px-2 py-1 text-xs',
                    a.level === 'critical' && 'border-destructive/40 text-destructive',
                    a.level === 'warning' && 'border-accent text-foreground',
                  )}
                >
                  <AlertIcon level={a.level} />
                  <span>{a.message}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section aria-label="Anti-thesis" className="rounded-md border border-dashed border-border bg-muted/30 p-2">
          <p className="flex items-center gap-1 text-xs uppercase text-muted-foreground">
            <Target className="size-3" aria-hidden /> What kills this trade
          </p>
          <p className="text-sm">{card.anti_thesis}</p>
        </section>
      </CardContent>
    </Card>
  );
}

const TradeCardsToday: React.FC = () => {
  const query = useQuery<TradeCardsResponse, Error>({
    queryKey: ['trade-cards-today'],
    queryFn: async () => {
      const res = await api.get<TradeCardsResponse>('/trade-cards/today?limit=20&offset=0');
      return res.data;
    },
  });

  if (query.isLoading) {
    return (
      <div
        className="mx-auto max-w-4xl space-y-3 p-4"
        data-testid="trade-cards-loading"
      >
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="mx-auto max-w-4xl p-4" data-testid="trade-cards-error">
        <Alert variant="destructive">
          <AlertTriangle className="size-4" aria-hidden />
          <AlertTitle>Unable to load trade cards</AlertTitle>
          <AlertDescription>
            We couldn't reach the trade-cards service. Refresh to try again; if it keeps failing,
            check the admin health panel.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const data = query.data;
  const items = data?.items ?? [];
  const errors = data?.errors ?? [];

  if (items.length === 0) {
    return (
      <div
        className="mx-auto max-w-4xl space-y-3 p-4"
        data-testid="trade-cards-empty"
      >
        <div>
          <h1 className="font-heading text-xl font-semibold tracking-tight">Today's Trade Cards</h1>
          <p className="text-sm text-muted-foreground">
            One-screen, ranked plans built from today's scored candidates.
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-8 text-center text-sm text-muted-foreground">
            <ClipboardList className="size-8 text-muted-foreground" aria-hidden />
            <p className="max-w-md font-medium text-foreground">
              No trade cards today — the market did not hand us a plan worth printing.
            </p>
            <p className="max-w-md text-xs">
              The list stays empty when there are no scored candidates, or the quality gate
              quieted all of them. The next run may tell a different story.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4" data-testid="trade-cards-data">
      <div>
        <h1 className="font-heading text-xl font-semibold tracking-tight">Today's Trade Cards</h1>
        <p className="text-sm text-muted-foreground">
          Ranked by pick score. Each card shows the contract pick, three limit tiers, sizing for
          your account, and exit rules.
        </p>
      </div>

      {errors.length > 0 ? (
        <Alert variant="destructive" data-testid="trade-cards-partial-errors">
          <AlertTriangle className="size-4" aria-hidden />
          <AlertTitle>Some cards could not be composed</AlertTitle>
          <AlertDescription>
            <ul className="list-inside list-disc text-xs">
              {errors.map((e) => (
                <li key={`err-${e.candidate_id}`}>
                  {e.symbol}: {e.error}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      {items.map((card) => (
        <TradeCardRow key={card.candidate_id} card={card} />
      ))}
    </div>
  );
};

export default TradeCardsToday;
