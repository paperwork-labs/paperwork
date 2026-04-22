import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Download, Loader2, Search } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import PageHeader from '../../components/ui/PageHeader';
import { portfolioApi } from '../../services/api';
import { usePortfolioInsights, useRealizedGains } from '../../hooks/usePortfolio';
import { OpenOptionsSection } from '../../components/portfolio/OpenOptionsSection';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney, formatDateFriendly } from '../../utils/format';
import { TableSkeleton } from '../../components/shared/Skeleton';
import StatCard from '../../components/shared/StatCard';
import TradeModal from '../../components/orders/TradeModal';
import { TAX_RATE_SHORT_TERM_PCT, TAX_RATE_LONG_TERM_PCT } from '../../constants/tax';
import { useColorMode } from '../../theme/colorMode';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';

type TradeTarget = { symbol: string; currentPrice: number; sharesHeld: number; averageCost?: number } | null;

interface TaxLotRow {
  id: number;
  symbol: string;
  shares: number;
  purchase_date: string | null;
  cost_per_share: number;
  cost_basis?: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  is_long_term: boolean;
  days_held: number;
  approaching_lt: boolean;
  source?: string;
  commission?: number;
}

interface TaxSummary {
  total_lots: number;
  lt_lots: number;
  st_lots: number;
  lt_unrealized_gains: number;
  lt_unrealized_losses: number;
  st_unrealized_gains: number;
  st_unrealized_losses: number;
  estimated_lt_tax: number;
  estimated_st_tax: number;
  estimated_total_tax: number;
  net_harvest_potential: number;
}

type SortField = 'symbol' | 'days_held' | 'unrealized_pnl' | 'market_value';

type TabId = 'unrealized' | 'realized';

interface RealizedGainRow {
  symbol: string;
  tax_year: number;
  realized_pnl: number;
  cost_basis: number;
  proceeds: number;
  shares_sold: number;
  trade_count: number;
  lt_count: number;
  st_count: number;
  is_long_term: boolean;
}

interface YearSummary {
  year: number;
  st_gains: number;
  st_losses: number;
  lt_gains: number;
  lt_losses: number;
  total_realized: number;
  estimated_tax: number;
}

const thSort = 'cursor-pointer select-none hover:text-foreground';

const PortfolioTaxCenter: React.FC = () => {
  const { currency, timezone } = useUserPreferences();
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  const [activeTab, setActiveTab] = useState<TabId>('unrealized');
  const [search, setSearch] = useState('');
  const [tradeTarget, setTradeTarget] = useState<TradeTarget>(null);
  const [filter, setFilter] = useState<'all' | 'lt' | 'st' | 'harvest' | 'approaching'>('all');
  const [sortBy, setSortBy] = useState<SortField>('days_held');
  const [sortDesc, setSortDesc] = useState(true);
  const [openYears, setOpenYears] = useState<Set<number>>(new Set([new Date().getFullYear()]));

  const realizedQuery = useRealizedGains();
  const realizedGains: RealizedGainRow[] = realizedQuery.data?.realized_gains ?? [];
  const yearSummaries: YearSummary[] = realizedQuery.data?.summary_by_year ?? [];
  const realizedReady = !realizedQuery.isPending && !realizedQuery.isError;

  const gainsByYear = useMemo(() => {
    const m = new Map<number, RealizedGainRow[]>();
    for (const rg of realizedGains) {
      const arr = m.get(rg.tax_year) || [];
      arr.push(rg);
      m.set(rg.tax_year, arr);
    }
    return m;
  }, [realizedGains]);

  const toggleYear = (yr: number) => {
    setOpenYears((prev) => {
      const next = new Set(prev);
      if (next.has(yr)) next.delete(yr);
      else next.add(yr);
      return next;
    });
  };

  const handleExport = (year: number) => {
    const url = `/api/v1/portfolio/tax-report/export?year=${year}`;
    window.open(url, '_blank');
  };

  const taxQuery = useQuery({
    queryKey: ['taxSummary'],
    queryFn: async () => {
      const r = await portfolioApi.getTaxSummary();
      const raw = r as Record<string, unknown> | undefined;
      const data = (raw?.data as Record<string, unknown> | undefined)?.data ?? raw?.data ?? raw;
      return data as { tax_lots: TaxLotRow[]; summary: TaxSummary } | null;
    },
    staleTime: 60000,
  });

  const insightsQuery = usePortfolioInsights();
  const insights = insightsQuery.data;

  const lots = taxQuery.data?.tax_lots ?? [];
  const summary = taxQuery.data?.summary;

  const filteredLots = useMemo(() => {
    let result = lots;
    const q = search.trim().toLowerCase();
    if (q) result = result.filter((l) => l.symbol.toLowerCase().includes(q));

    switch (filter) {
      case 'lt':
        result = result.filter((l) => l.is_long_term);
        break;
      case 'st':
        result = result.filter((l) => !l.is_long_term);
        break;
      case 'harvest':
        result = result.filter((l) => l.unrealized_pnl < -1000);
        break;
      case 'approaching':
        result = result.filter((l) => l.approaching_lt);
        break;
    }

    result = [...result].sort((a, b) => {
      const av = a[sortBy];
      const bv = b[sortBy];
      if (typeof av === 'string' && typeof bv === 'string')
        return sortDesc ? bv.localeCompare(av) : av.localeCompare(bv);
      return sortDesc ? Number(bv) - Number(av) : Number(av) - Number(bv);
    });

    return result;
  }, [lots, search, filter, sortBy, sortDesc]);

  const toggleSort = (field: SortField) => {
    if (sortBy === field) setSortDesc(!sortDesc);
    else {
      setSortBy(field);
      setSortDesc(true);
    }
  };

  if (taxQuery.isPending) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <PageHeader title="Tax Center" subtitle="Tax lot analysis, harvesting candidates, and estimated tax impact" />
        <TableSkeleton rows={8} cols={6} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <PageHeader title="Tax Center" subtitle="Tax lot analysis, harvesting candidates, and estimated tax impact" />
      <p className="text-xs text-muted-foreground">
        Estimated tax uses the short- and long-term rates labeled on each card (U.S. federal assumptions for those
        percentages). This is not tax advice. State and local taxes are not included.
      </p>

      <div className="flex gap-2">
        <Button
          size="sm"
          variant={activeTab === 'unrealized' ? 'default' : 'outline'}
          className={activeTab === 'unrealized' ? 'bg-amber-500 text-amber-950 hover:bg-amber-400' : ''}
          onClick={() => setActiveTab('unrealized')}
        >
          Unrealized
        </Button>
        <Button
          size="sm"
          variant={activeTab === 'realized' ? 'default' : 'outline'}
          className={activeTab === 'realized' ? 'bg-amber-500 text-amber-950 hover:bg-amber-400' : ''}
          onClick={() => setActiveTab('realized')}
        >
          Realized Gains
        </Button>
      </div>

      <OpenOptionsSection />

      {activeTab === 'realized' && (
        <div className="flex flex-col gap-4">
          {realizedQuery.isPending && (
            <Card className="gap-0 border border-border shadow-none ring-0">
              <CardContent className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Loading realized gains…
              </CardContent>
            </Card>
          )}
          {realizedQuery.isError && (
            <Card className="gap-0 border border-destructive/40 shadow-none ring-0">
              <CardContent className="flex flex-col gap-3 py-6 text-sm">
                <span className="font-semibold text-foreground">Could not load realized gains</span>
                <span className="text-muted-foreground">This is usually a transient error. Try again in a moment.</span>
                <div>
                  <Button type="button" size="sm" onClick={() => void realizedQuery.refetch()}>
                    Retry
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
          {realizedReady && yearSummaries.length > 0 && (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {yearSummaries.slice(0, 1).map((s) => (
                <React.Fragment key={s.year}>
                  <StatCard
                    label={`${s.year} Total Realized`}
                    value={formatMoney(s.total_realized, currency, { maximumFractionDigits: 0 })}
                    color={s.total_realized >= 0 ? 'status.success' : 'status.danger'}
                  />
                  <StatCard
                    label="ST Gains"
                    value={formatMoney(s.st_gains, currency, { maximumFractionDigits: 0 })}
                    sub={`Losses: ${formatMoney(s.st_losses, currency, { maximumFractionDigits: 0 })}`}
                    color="status.warning"
                  />
                  <StatCard
                    label="LT Gains"
                    value={formatMoney(s.lt_gains, currency, { maximumFractionDigits: 0 })}
                    sub={`Losses: ${formatMoney(s.lt_losses, currency, { maximumFractionDigits: 0 })}`}
                    color="status.success"
                  />
                  <StatCard
                    label="Est. Tax"
                    value={formatMoney(s.estimated_tax, currency, { maximumFractionDigits: 0 })}
                    sub={`ST @ ${TAX_RATE_SHORT_TERM_PCT}% / LT @ ${TAX_RATE_LONG_TERM_PCT}%`}
                    color="status.danger"
                  />
                </React.Fragment>
              ))}
            </div>
          )}

          {realizedReady && yearSummaries.map((ys) => {
            const yearRows = gainsByYear.get(ys.year) || [];
            const isOpen = openYears.has(ys.year);
            return (
              <Card key={ys.year} className="gap-0 border border-border shadow-none ring-0">
                <CardHeader className="pb-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <button
                      type="button"
                      className="flex flex-wrap items-center gap-2 text-left"
                      onClick={() => toggleYear(ys.year)}
                    >
                      {isOpen ? <ChevronDown className="size-4" aria-hidden /> : <ChevronRight className="size-4" aria-hidden />}
                      <span className="font-bold">{ys.year}</span>
                      <Badge variant="outline" className="h-5">
                        {yearRows.length} symbols
                      </Badge>
                      <span
                        className={cn(
                          'text-sm font-semibold',
                          semanticTextColorClass(ys.total_realized >= 0 ? 'fg.success' : 'fg.error'),
                        )}
                      >
                        {formatMoney(ys.total_realized, currency, { maximumFractionDigits: 0 })}
                      </span>
                    </button>
                    <Button size="xs" variant="outline" className="gap-1" onClick={() => handleExport(ys.year)}>
                      <Download className="size-3.5" aria-hidden />
                      CSV
                    </Button>
                  </div>
                </CardHeader>
                {isOpen && (
                  <CardContent className="px-0 pb-4">
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-sm">
                        <thead>
                          <tr className="border-b border-border text-left text-xs text-muted-foreground">
                            <th className="p-2 font-medium">Symbol</th>
                            <th className="p-2 text-end font-medium">Shares Sold</th>
                            <th className="p-2 text-end font-medium">Proceeds</th>
                            <th className="p-2 text-end font-medium">Cost Basis</th>
                            <th className="p-2 text-end font-medium">Realized P&L</th>
                            <th className="p-2 font-medium">Term</th>
                            <th className="p-2 text-end font-medium">Trades</th>
                          </tr>
                        </thead>
                        <tbody>
                          {yearRows.map((rg, i) => (
                            <tr key={`${rg.symbol}-${i}`} className="border-b border-border/60">
                              <td className="p-2 font-mono font-semibold">{rg.symbol}</td>
                              <td className="p-2 text-end">{rg.shares_sold.toLocaleString()}</td>
                              <td className="p-2 text-end">
                                {formatMoney(rg.proceeds, currency, { maximumFractionDigits: 0 })}
                              </td>
                              <td className="p-2 text-end">
                                {formatMoney(rg.cost_basis, currency, { maximumFractionDigits: 0 })}
                              </td>
                              <td
                                className={cn(
                                  'p-2 text-end',
                                  semanticTextColorClass(rg.realized_pnl >= 0 ? 'fg.success' : 'fg.error'),
                                )}
                              >
                                {formatMoney(rg.realized_pnl, currency, { maximumFractionDigits: 0 })}
                              </td>
                              <td className="p-2">
                                <Badge
                                  variant="outline"
                                  className={cn(
                                    'h-5 text-[10px]',
                                    rg.is_long_term
                                      ? 'border-emerald-500/40 bg-emerald-500/10'
                                      : 'border-border bg-muted/50',
                                  )}
                                >
                                  {rg.lt_count > 0 && rg.st_count > 0 ? 'Mixed' : rg.is_long_term ? 'LT' : 'ST'}
                                </Badge>
                              </td>
                              <td className="p-2 text-end">{rg.trade_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="flex flex-wrap gap-4 border-t border-border p-3 text-xs text-muted-foreground">
                      <span>
                        ST Gains:{' '}
                        <span className="font-bold text-foreground">
                          {formatMoney(ys.st_gains, currency, { maximumFractionDigits: 0 })}
                        </span>
                      </span>
                      <span>
                        ST Losses:{' '}
                        <span className={cn('font-bold', semanticTextColorClass('fg.error'))}>
                          {formatMoney(ys.st_losses, currency, { maximumFractionDigits: 0 })}
                        </span>
                      </span>
                      <span>
                        LT Gains:{' '}
                        <span className="font-bold text-foreground">
                          {formatMoney(ys.lt_gains, currency, { maximumFractionDigits: 0 })}
                        </span>
                      </span>
                      <span>
                        LT Losses:{' '}
                        <span className={cn('font-bold', semanticTextColorClass('fg.error'))}>
                          {formatMoney(ys.lt_losses, currency, { maximumFractionDigits: 0 })}
                        </span>
                      </span>
                      <span>
                        Est. Tax:{' '}
                        <span className={cn('font-bold', semanticTextColorClass('fg.error'))}>
                          {formatMoney(ys.estimated_tax, currency, { maximumFractionDigits: 0 })}
                        </span>
                      </span>
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })}

          {realizedReady && realizedGains.length === 0 && (
            <Card className="gap-0 border border-border shadow-none ring-0">
              <CardContent className="py-6 text-center text-sm text-muted-foreground">
                No realized gains data. Sell trades from IBKR FlexQuery will appear here after sync.
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'unrealized' && summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-5">
          <StatCard label="Total Lots" value={summary.total_lots} sub={`${summary.lt_lots} LT · ${summary.st_lots} ST`} />
          <StatCard
            label="ST Unrealized"
            value={formatMoney(summary.st_unrealized_gains + summary.st_unrealized_losses, currency, {
              maximumFractionDigits: 0,
            })}
            sub={`Est. tax ${formatMoney(summary.estimated_st_tax, currency, { maximumFractionDigits: 0 })} @ ${TAX_RATE_SHORT_TERM_PCT}%`}
            color={
              summary.st_unrealized_gains + summary.st_unrealized_losses >= 0 ? 'status.success' : 'status.danger'
            }
          />
          <StatCard
            label="LT Unrealized"
            value={formatMoney(summary.lt_unrealized_gains + summary.lt_unrealized_losses, currency, {
              maximumFractionDigits: 0,
            })}
            sub={`Est. tax ${formatMoney(summary.estimated_lt_tax, currency, { maximumFractionDigits: 0 })} @ ${TAX_RATE_LONG_TERM_PCT}%`}
            color={
              summary.lt_unrealized_gains + summary.lt_unrealized_losses >= 0 ? 'status.success' : 'status.danger'
            }
          />
          <StatCard
            label="Est. Total Tax"
            value={formatMoney(summary.estimated_total_tax, currency, { maximumFractionDigits: 0 })}
            color="status.warning"
          />
          <StatCard
            label="Harvest Potential"
            value={formatMoney(summary.net_harvest_potential, currency, { maximumFractionDigits: 0 })}
            sub="Unrealized losses"
            color="status.danger"
          />
        </div>
      )}

      {activeTab === 'unrealized' && insightsQuery.isPending && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="border border-border shadow-none ring-0">
            <CardContent className="py-4 text-sm text-muted-foreground">Loading tax insights…</CardContent>
          </Card>
          <Card className="border border-border shadow-none ring-0">
            <CardContent className="py-4 text-sm text-muted-foreground">Loading tax insights…</CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'unrealized' && insightsQuery.isError && (
        <Card className="border border-border shadow-none ring-0">
          <CardContent className={cn('py-4 text-sm', semanticTextColorClass('status.danger'))}>
            Failed to load tax insights
          </CardContent>
        </Card>
      )}

      {activeTab === 'unrealized' &&
        insights &&
        (insights.harvest_candidates?.length > 0 || insights.approaching_lt?.length > 0) && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {insights.harvest_candidates && insights.harvest_candidates.length > 0 && (
              <Card className="gap-0 border border-border shadow-none ring-0">
                <CardHeader className="pb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">Tax Loss Harvesting Candidates</span>
                    <Badge variant="destructive" className="h-5 text-[10px]">
                      {insights.harvest_candidates.length}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-1 pt-2">
                  {insights.harvest_candidates.map((c) => (
                    <div key={c.symbol} className="flex justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-bold">{c.symbol}</span>
                        <span className="text-xs text-muted-foreground">
                          {c.shares} sh · {c.days_held}d held
                        </span>
                      </div>
                      <span className={cn('text-sm font-semibold', semanticTextColorClass('fg.error'))}>
                        {formatMoney(c.unrealized_pnl, currency, { maximumFractionDigits: 0 })}
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {insights.approaching_lt && insights.approaching_lt.length > 0 && (
              <Card className="gap-0 border border-border shadow-none ring-0">
                <CardHeader className="pb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">Approaching Long-Term Status</span>
                    <Badge
                      variant="outline"
                      className="h-5 border-amber-500/40 bg-amber-500/10 text-[10px] text-amber-900 dark:text-amber-100"
                    >
                      {insights.approaching_lt.length}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-1 pt-2">
                  {insights.approaching_lt.map((p) => (
                    <div key={p.symbol} className="flex justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-bold">{p.symbol}</span>
                        <span className="text-xs text-muted-foreground">
                          {p.shares} sh · {p.days_held}d held
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className="h-5 border-amber-500/40 bg-amber-500/10 text-[10px]"
                        >
                          {p.days_to_lt}d to LT
                        </Badge>
                        <span
                          className={cn(
                            'text-xs',
                            semanticTextColorClass(p.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error'),
                          )}
                        >
                          {formatMoney(p.unrealized_pnl, currency, { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}

      {activeTab === 'unrealized' && (
        <Card className="gap-0 border border-border shadow-none ring-0">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="font-bold">All Tax Lots</span>
                <Badge variant="outline" className="h-5">
                  {filteredLots.length}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative flex items-center">
                  <Search
                    className="pointer-events-none absolute left-2 size-4 text-muted-foreground"
                    aria-hidden
                  />
                  <Input
                    className="h-8 w-[160px] pl-8 text-sm"
                    placeholder="Filter symbol..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                {(['all', 'lt', 'st', 'harvest', 'approaching'] as const).map((f) => (
                  <Button key={f} size="xs" variant={filter === f ? 'default' : 'outline'} onClick={() => setFilter(f)}>
                    {f === 'all'
                      ? 'All'
                      : f === 'lt'
                        ? 'Long Term'
                        : f === 'st'
                          ? 'Short Term'
                          : f === 'harvest'
                            ? 'Harvest'
                            : 'Near LT'}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <div className="max-h-[calc(100vh-420px)] overflow-auto">
              <table className="w-full border-collapse text-sm">
                <thead className="sticky top-0 z-10 bg-card">
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className={cn('p-2 font-medium', thSort)} onClick={() => toggleSort('symbol')}>
                      Symbol {sortBy === 'symbol' ? (sortDesc ? '↓' : '↑') : ''}
                    </th>
                    <th className="p-2 font-medium">Type</th>
                    <th className={cn('p-2 text-end font-medium', thSort)} onClick={() => toggleSort('days_held')}>
                      Days {sortBy === 'days_held' ? (sortDesc ? '↓' : '↑') : ''}
                    </th>
                    <th className="p-2 font-medium">Date</th>
                    <th className="p-2 text-end font-medium">Shares</th>
                    <th className="p-2 text-end font-medium">Cost/Sh</th>
                    <th className="p-2 text-end font-medium">Cost Basis</th>
                    <th className={cn('p-2 text-end font-medium', thSort)} onClick={() => toggleSort('market_value')}>
                      Value {sortBy === 'market_value' ? (sortDesc ? '↓' : '↑') : ''}
                    </th>
                    <th className={cn('p-2 text-end font-medium', thSort)} onClick={() => toggleSort('unrealized_pnl')}>
                      P/L {sortBy === 'unrealized_pnl' ? (sortDesc ? '↓' : '↑') : ''}
                    </th>
                    <th className="p-2 text-end font-medium">P/L %</th>
                    <th className="p-2 font-medium">Source</th>
                    <th className="w-[60px] p-2" />
                  </tr>
                </thead>
                <tbody>
                  {filteredLots.map((l) => {
                    const daysToLT = Math.max(0, 365 - l.days_held);
                    return (
                      <tr
                        key={l.id}
                        className={cn(
                          'border-b border-border/60',
                          l.approaching_lt && (isDark ? 'bg-amber-950/25' : 'bg-amber-50'),
                        )}
                      >
                        <td className="p-2 font-mono font-semibold">{l.symbol}</td>
                        <td className="p-2">
                          <Badge
                            variant="outline"
                            className={cn(
                              'h-5 text-[10px]',
                              l.is_long_term
                                ? 'border-emerald-500/40 bg-emerald-500/10'
                                : l.approaching_lt
                                  ? 'border-amber-500/40 bg-amber-500/10'
                                  : 'border-border bg-muted/50',
                            )}
                          >
                            {l.is_long_term ? 'LT' : 'ST'}
                          </Badge>
                        </td>
                        <td className="p-2 text-end">
                          <span
                            className={cn(
                              'text-xs',
                              l.approaching_lt
                                ? semanticTextColorClass(isDark ? 'yellow.400' : 'yellow.700')
                                : 'text-muted-foreground',
                            )}
                          >
                            {l.days_held}d
                            {l.approaching_lt && (
                              <span
                                className={cn(semanticTextColorClass(isDark ? 'yellow.400' : 'yellow.700'))}
                              >
                                {' '}
                                ({daysToLT}d to LT)
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="p-2">{formatDateFriendly(l.purchase_date, timezone)}</td>
                        <td className="p-2 text-end">{l.shares.toLocaleString()}</td>
                        <td className="p-2 text-end">{formatMoney(l.cost_per_share, currency)}</td>
                        <td className="p-2 text-end">
                          {l.cost_basis != null
                            ? formatMoney(l.cost_basis, currency, { maximumFractionDigits: 0 })
                            : '—'}
                        </td>
                        <td className="p-2 text-end">
                          {formatMoney(l.market_value, currency, { maximumFractionDigits: 0 })}
                        </td>
                        <td
                          className={cn(
                            'p-2 text-end',
                            semanticTextColorClass(l.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error'),
                          )}
                        >
                          {formatMoney(l.unrealized_pnl, currency, { maximumFractionDigits: 0 })}
                        </td>
                        <td
                          className={cn(
                            'p-2 text-end',
                            semanticTextColorClass(l.unrealized_pnl_pct >= 0 ? 'fg.success' : 'fg.error'),
                          )}
                        >
                          {l.unrealized_pnl_pct.toFixed(1)}%
                        </td>
                        <td className="p-2">
                          {l.source && (
                            <Badge
                              variant="outline"
                              className={cn(
                                'h-5 text-[10px]',
                                l.source === 'official_statement'
                                  ? 'border-primary/40 bg-primary/10'
                                  : 'border-border bg-muted/50',
                              )}
                            >
                              {l.source === 'official_statement' ? 'Official' : 'Estimated'}
                            </Badge>
                          )}
                        </td>
                        <td className="p-2">
                          <Button
                            size="xs"
                            variant="outline"
                            className="h-7 border-destructive/40 text-destructive hover:bg-destructive/10"
                            onClick={() =>
                              setTradeTarget({
                                symbol: l.symbol,
                                currentPrice: l.shares > 0 ? l.market_value / l.shares : 0,
                                sharesHeld: l.shares,
                                averageCost: l.cost_per_share,
                              })
                            }
                          >
                            Sell
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                {filteredLots.length > 0 &&
                  (() => {
                    const totals = filteredLots.reduce(
                      (acc, l) => ({
                        shares: acc.shares + l.shares,
                        cost_basis: acc.cost_basis + (l.cost_basis ?? 0),
                        market_value: acc.market_value + l.market_value,
                        unrealized_pnl: acc.unrealized_pnl + l.unrealized_pnl,
                      }),
                      { shares: 0, cost_basis: 0, market_value: 0, unrealized_pnl: 0 },
                    );
                    const totalPnlPct = totals.cost_basis ? (totals.unrealized_pnl / totals.cost_basis) * 100 : 0;
                    return (
                      <tfoot>
                        <tr className="border-t border-border bg-muted/40 font-semibold">
                          <td className="p-2">Total</td>
                          <td className="p-2" />
                          <td className="p-2" />
                          <td className="p-2" />
                          <td className="p-2 text-end">{totals.shares.toLocaleString()}</td>
                          <td className="p-2" />
                          <td className="p-2 text-end">
                            {formatMoney(totals.cost_basis, currency, { maximumFractionDigits: 0 })}
                          </td>
                          <td className="p-2 text-end">
                            {formatMoney(totals.market_value, currency, { maximumFractionDigits: 0 })}
                          </td>
                          <td
                            className={cn(
                              'p-2 text-end',
                              semanticTextColorClass(totals.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error'),
                            )}
                          >
                            {formatMoney(totals.unrealized_pnl, currency, { maximumFractionDigits: 0 })}
                          </td>
                          <td
                            className={cn(
                              'p-2 text-end',
                              semanticTextColorClass(totalPnlPct >= 0 ? 'fg.success' : 'fg.error'),
                            )}
                          >
                            {totalPnlPct.toFixed(1)}%
                          </td>
                          <td className="p-2" />
                          <td className="p-2" />
                        </tr>
                      </tfoot>
                    );
                  })()}
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {tradeTarget && (
        <TradeModal
          isOpen={!!tradeTarget}
          symbol={tradeTarget.symbol}
          currentPrice={tradeTarget.currentPrice}
          sharesHeld={tradeTarget.sharesHeld}
          averageCost={tradeTarget.averageCost}
          onClose={() => setTradeTarget(null)}
        />
      )}
    </div>
  );
};

export default PortfolioTaxCenter;
