import React, { useMemo, useState } from 'react';
import {
  Box,
  Text,
  Badge,
  CardRoot,
  CardBody,
  CardHeader,
  Button,
  HStack,
  VStack,
  SimpleGrid,
  TableScrollArea,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
  Input,
  InputGroup,
  Collapsible,
} from '@chakra-ui/react';
import { FiSearch, FiDownload, FiChevronDown, FiChevronRight } from 'react-icons/fi';
import { useQuery } from 'react-query';
import PageHeader from '../../components/ui/PageHeader';
import { portfolioApi, unwrapResponseSingle } from '../../services/api';
import { usePortfolioInsights, useRealizedGains } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';
import { TableSkeleton } from '../../components/shared/Skeleton';
import StatCard from '../../components/shared/StatCard';
import { TAX_RATE_SHORT_TERM_PCT, TAX_RATE_LONG_TERM_PCT } from '../../constants/tax';

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

const PortfolioTaxCenter: React.FC = () => {
  const { currency } = useUserPreferences();
  const [activeTab, setActiveTab] = useState<TabId>('unrealized');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'lt' | 'st' | 'harvest' | 'approaching'>('all');
  const [sortBy, setSortBy] = useState<SortField>('days_held');
  const [sortDesc, setSortDesc] = useState(true);
  const [openYears, setOpenYears] = useState<Set<number>>(new Set([new Date().getFullYear()]));

  const realizedQuery = useRealizedGains();
  const realizedGains: RealizedGainRow[] = realizedQuery.data?.realized_gains ?? [];
  const yearSummaries: YearSummary[] = realizedQuery.data?.summary_by_year ?? [];

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
    setOpenYears(prev => {
      const next = new Set(prev);
      if (next.has(yr)) next.delete(yr); else next.add(yr);
      return next;
    });
  };

  const handleExport = (year: number) => {
    const url = `/api/v1/portfolio/tax-report/export?year=${year}`;
    window.open(url, '_blank');
  };

  const taxQuery = useQuery('taxSummary', async () => {
    const r = await portfolioApi.getTaxSummary();
    const raw = r as Record<string, any> | undefined;
    const data = raw?.data?.data ?? raw?.data ?? raw;
    return data as { tax_lots: TaxLotRow[]; summary: TaxSummary } | null;
  }, { staleTime: 60000 });

  const insightsQuery = usePortfolioInsights();
  const insights = insightsQuery.data;

  const lots = taxQuery.data?.tax_lots ?? [];
  const summary = taxQuery.data?.summary;

  const filteredLots = useMemo(() => {
    let result = lots;
    const q = search.trim().toLowerCase();
    if (q) result = result.filter((l) => l.symbol.toLowerCase().includes(q));

    switch (filter) {
      case 'lt': result = result.filter((l) => l.is_long_term); break;
      case 'st': result = result.filter((l) => !l.is_long_term); break;
      case 'harvest': result = result.filter((l) => l.unrealized_pnl < -1000); break;
      case 'approaching': result = result.filter((l) => l.approaching_lt); break;
    }

    result = [...result].sort((a, b) => {
      const av = a[sortBy];
      const bv = b[sortBy];
      if (typeof av === 'string' && typeof bv === 'string') return sortDesc ? bv.localeCompare(av) : av.localeCompare(bv);
      return sortDesc ? (Number(bv) - Number(av)) : (Number(av) - Number(bv));
    });

    return result;
  }, [lots, search, filter, sortBy, sortDesc]);

  const toggleSort = (field: SortField) => {
    if (sortBy === field) setSortDesc(!sortDesc);
    else { setSortBy(field); setSortDesc(true); }
  };

  const fmtDate = (iso: string | null) => {
    if (!iso) return '-';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '-' : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: '2-digit' });
  };

  if (taxQuery.isLoading) {
    return (
      <VStack p={6} gap={6} align="stretch">
        <PageHeader title="Tax Center" subtitle="Tax lot analysis, harvesting candidates, and estimated tax impact" />
        <TableSkeleton rows={8} cols={6} />
      </VStack>
    );
  }

  return (
    <VStack p={6} gap={4} align="stretch">
      <PageHeader title="Tax Center" subtitle="Tax lot analysis, harvesting candidates, and estimated tax impact" />

      <HStack gap={2}>
        <Button size="sm" variant={activeTab === 'unrealized' ? 'solid' : 'outline'} onClick={() => setActiveTab('unrealized')}>
          Unrealized
        </Button>
        <Button size="sm" variant={activeTab === 'realized' ? 'solid' : 'outline'} colorPalette={activeTab === 'realized' ? 'brand' : undefined} onClick={() => setActiveTab('realized')}>
          Realized Gains
        </Button>
      </HStack>

      {activeTab === 'realized' && (
        <VStack gap={4} align="stretch">
          {yearSummaries.length > 0 && (
            <SimpleGrid columns={{ base: 2, md: 4 }} gap={3}>
              {yearSummaries.slice(0, 1).map(s => (
                <React.Fragment key={s.year}>
                  <StatCard label={`${s.year} Total Realized`} value={formatMoney(s.total_realized, currency, { maximumFractionDigits: 0 })} color={s.total_realized >= 0 ? 'status.success' : 'status.danger'} />
                  <StatCard label="ST Gains" value={formatMoney(s.st_gains, currency, { maximumFractionDigits: 0 })} sub={`Losses: ${formatMoney(s.st_losses, currency, { maximumFractionDigits: 0 })}`} color="status.warning" />
                  <StatCard label="LT Gains" value={formatMoney(s.lt_gains, currency, { maximumFractionDigits: 0 })} sub={`Losses: ${formatMoney(s.lt_losses, currency, { maximumFractionDigits: 0 })}`} color="status.success" />
                  <StatCard label="Est. Tax" value={formatMoney(s.estimated_tax, currency, { maximumFractionDigits: 0 })} sub={`ST @ ${TAX_RATE_SHORT_TERM_PCT}% / LT @ ${TAX_RATE_LONG_TERM_PCT}%`} color="status.danger" />
                </React.Fragment>
              ))}
            </SimpleGrid>
          )}

          {yearSummaries.map(ys => {
            const yearRows = gainsByYear.get(ys.year) || [];
            const isOpen = openYears.has(ys.year);
            return (
              <CardRoot key={ys.year} bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                <CardHeader pb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <HStack gap={2} cursor="pointer" onClick={() => toggleYear(ys.year)}>
                      {isOpen ? <FiChevronDown /> : <FiChevronRight />}
                      <Text fontWeight="bold">{ys.year}</Text>
                      <Badge variant="outline">{yearRows.length} symbols</Badge>
                      <Text fontSize="sm" color={ys.total_realized >= 0 ? 'fg.success' : 'fg.error'} fontWeight="semibold">
                        {formatMoney(ys.total_realized, currency, { maximumFractionDigits: 0 })}
                      </Text>
                    </HStack>
                    <Button size="xs" variant="outline" onClick={() => handleExport(ys.year)}>
                      <FiDownload /> CSV
                    </Button>
                  </Box>
                </CardHeader>
                {isOpen && (
                  <CardBody p={0}>
                    <TableScrollArea>
                      <TableRoot size="sm">
                        <TableHeader>
                          <TableRow>
                            <TableColumnHeader>Symbol</TableColumnHeader>
                            <TableColumnHeader textAlign="end">Shares Sold</TableColumnHeader>
                            <TableColumnHeader textAlign="end">Proceeds</TableColumnHeader>
                            <TableColumnHeader textAlign="end">Cost Basis</TableColumnHeader>
                            <TableColumnHeader textAlign="end">Realized P&L</TableColumnHeader>
                            <TableColumnHeader>Term</TableColumnHeader>
                            <TableColumnHeader textAlign="end">Trades</TableColumnHeader>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {yearRows.map((rg, i) => (
                            <TableRow key={`${rg.symbol}-${i}`}>
                              <TableCell><Text fontFamily="mono" fontWeight="semibold">{rg.symbol}</Text></TableCell>
                              <TableCell textAlign="end">{rg.shares_sold.toLocaleString()}</TableCell>
                              <TableCell textAlign="end">{formatMoney(rg.proceeds, currency, { maximumFractionDigits: 0 })}</TableCell>
                              <TableCell textAlign="end">{formatMoney(rg.cost_basis, currency, { maximumFractionDigits: 0 })}</TableCell>
                              <TableCell textAlign="end" color={rg.realized_pnl >= 0 ? 'fg.success' : 'fg.error'}>
                                {formatMoney(rg.realized_pnl, currency, { maximumFractionDigits: 0 })}
                              </TableCell>
                              <TableCell>
                                <Badge size="sm" colorPalette={rg.is_long_term ? 'green' : 'gray'}>
                                  {rg.lt_count > 0 && rg.st_count > 0 ? 'Mixed' : rg.is_long_term ? 'LT' : 'ST'}
                                </Badge>
                              </TableCell>
                              <TableCell textAlign="end">{rg.trade_count}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </TableRoot>
                    </TableScrollArea>
                    <Box p={3} borderTopWidth="1px" borderColor="border.subtle" display="flex" gap={4} flexWrap="wrap">
                      <Text fontSize="xs" color="fg.muted">ST Gains: <Text as="span" fontWeight="bold">{formatMoney(ys.st_gains, currency, { maximumFractionDigits: 0 })}</Text></Text>
                      <Text fontSize="xs" color="fg.muted">ST Losses: <Text as="span" fontWeight="bold" color="fg.error">{formatMoney(ys.st_losses, currency, { maximumFractionDigits: 0 })}</Text></Text>
                      <Text fontSize="xs" color="fg.muted">LT Gains: <Text as="span" fontWeight="bold">{formatMoney(ys.lt_gains, currency, { maximumFractionDigits: 0 })}</Text></Text>
                      <Text fontSize="xs" color="fg.muted">LT Losses: <Text as="span" fontWeight="bold" color="fg.error">{formatMoney(ys.lt_losses, currency, { maximumFractionDigits: 0 })}</Text></Text>
                      <Text fontSize="xs" color="fg.muted">Est. Tax: <Text as="span" fontWeight="bold" color="fg.error">{formatMoney(ys.estimated_tax, currency, { maximumFractionDigits: 0 })}</Text></Text>
                    </Box>
                  </CardBody>
                )}
              </CardRoot>
            );
          })}

          {realizedGains.length === 0 && !realizedQuery.isLoading && (
            <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
              <CardBody><Text color="fg.muted" textAlign="center">No realized gains data. Sell trades from IBKR FlexQuery will appear here after sync.</Text></CardBody>
            </CardRoot>
          )}
        </VStack>
      )}

      {activeTab === 'unrealized' && summary && (
        <SimpleGrid columns={{ base: 2, md: 4, lg: 5 }} gap={3}>
          <StatCard label="Total Lots" value={summary.total_lots} sub={`${summary.lt_lots} LT · ${summary.st_lots} ST`} />
          <StatCard
            label="ST Unrealized"
            value={formatMoney(summary.st_unrealized_gains + summary.st_unrealized_losses, currency, { maximumFractionDigits: 0 })}
            sub={`Est. tax ${formatMoney(summary.estimated_st_tax, currency, { maximumFractionDigits: 0 })} @ ${TAX_RATE_SHORT_TERM_PCT}%`}
            color={(summary.st_unrealized_gains + summary.st_unrealized_losses) >= 0 ? 'status.success' : 'status.danger'}
          />
          <StatCard
            label="LT Unrealized"
            value={formatMoney(summary.lt_unrealized_gains + summary.lt_unrealized_losses, currency, { maximumFractionDigits: 0 })}
            sub={`Est. tax ${formatMoney(summary.estimated_lt_tax, currency, { maximumFractionDigits: 0 })} @ ${TAX_RATE_LONG_TERM_PCT}%`}
            color={(summary.lt_unrealized_gains + summary.lt_unrealized_losses) >= 0 ? 'status.success' : 'status.danger'}
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
        </SimpleGrid>
      )}

      {activeTab === 'unrealized' && insightsQuery.isLoading && (
        <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
          <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
            <CardBody><Text fontSize="sm" color="fg.muted">Loading tax insights…</Text></CardBody>
          </CardRoot>
          <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
            <CardBody><Text fontSize="sm" color="fg.muted">Loading tax insights…</Text></CardBody>
          </CardRoot>
        </SimpleGrid>
      )}

      {activeTab === 'unrealized' && insightsQuery.isError && (
        <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
          <CardBody><Text fontSize="sm" color="status.danger">Failed to load tax insights</Text></CardBody>
        </CardRoot>
      )}

      {activeTab === 'unrealized' && insights && (insights.harvest_candidates?.length > 0 || insights.approaching_lt?.length > 0) && (
        <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
          {insights.harvest_candidates?.length > 0 && (
            <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
              <CardHeader pb={1}>
                <HStack gap={2}>
                  <Text fontSize="sm" fontWeight="semibold">Tax Loss Harvesting Candidates</Text>
                  <Badge size="sm" colorPalette="red">{insights.harvest_candidates.length}</Badge>
                </HStack>
              </CardHeader>
              <CardBody pt={2}>
                <VStack align="stretch" gap={1}>
                  {insights.harvest_candidates.map((c) => (
                    <HStack key={c.symbol} justify="space-between">
                      <HStack gap={2}>
                        <Text fontFamily="mono" fontSize="sm" fontWeight="bold">{c.symbol}</Text>
                        <Text fontSize="xs" color="fg.muted">{c.shares} sh · {c.days_held}d held</Text>
                      </HStack>
                      <Text fontSize="sm" color="fg.error" fontWeight="semibold">{formatMoney(c.unrealized_pnl, currency, { maximumFractionDigits: 0 })}</Text>
                    </HStack>
                  ))}
                </VStack>
              </CardBody>
            </CardRoot>
          )}

          {insights.approaching_lt?.length > 0 && (
            <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
              <CardHeader pb={1}>
                <HStack gap={2}>
                  <Text fontSize="sm" fontWeight="semibold">Approaching Long-Term Status</Text>
                  <Badge size="sm" colorPalette="yellow">{insights.approaching_lt.length}</Badge>
                </HStack>
              </CardHeader>
              <CardBody pt={2}>
                <VStack align="stretch" gap={1}>
                  {insights.approaching_lt.map((p) => (
                    <HStack key={p.symbol} justify="space-between">
                      <HStack gap={2}>
                        <Text fontFamily="mono" fontSize="sm" fontWeight="bold">{p.symbol}</Text>
                        <Text fontSize="xs" color="fg.muted">{p.shares} sh · {p.days_held}d held</Text>
                      </HStack>
                      <HStack gap={2}>
                        <Badge size="sm" colorPalette="yellow">{p.days_to_lt}d to LT</Badge>
                        <Text fontSize="xs" color={p.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error'}>
                          {formatMoney(p.unrealized_pnl, currency, { maximumFractionDigits: 0 })}
                        </Text>
                      </HStack>
                    </HStack>
                  ))}
                </VStack>
              </CardBody>
            </CardRoot>
          )}
        </SimpleGrid>
      )}

      {activeTab === 'unrealized' && (
      <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
        <CardHeader pb={2}>
          <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={3}>
            <HStack gap={2}>
              <Text fontWeight="bold">All Tax Lots</Text>
              <Badge variant="outline">{filteredLots.length}</Badge>
            </HStack>
            <HStack gap={2} flexWrap="wrap">
              <InputGroup
                startElement={
                  <Box color="fg.muted" display="flex" alignItems="center"><FiSearch /></Box>
                }
              >
                <Input placeholder="Filter symbol..." value={search} onChange={(e) => setSearch(e.target.value)} size="sm" w="160px" />
              </InputGroup>
              {(['all', 'lt', 'st', 'harvest', 'approaching'] as const).map((f) => (
                <Button key={f} size="xs" variant={filter === f ? 'solid' : 'outline'} onClick={() => setFilter(f)}>
                  {f === 'all' ? 'All' : f === 'lt' ? 'Long Term' : f === 'st' ? 'Short Term' : f === 'harvest' ? 'Harvest' : 'Near LT'}
                </Button>
              ))}
            </HStack>
          </Box>
        </CardHeader>
        <CardBody p={0}>
          <TableScrollArea maxH="calc(100vh - 420px)">
            <TableRoot size="sm">
              <TableHeader>
                <TableRow>
                  <TableColumnHeader cursor="pointer" onClick={() => toggleSort('symbol')}>
                    Symbol {sortBy === 'symbol' ? (sortDesc ? '↓' : '↑') : ''}
                  </TableColumnHeader>
                  <TableColumnHeader>Type</TableColumnHeader>
                  <TableColumnHeader cursor="pointer" textAlign="end" onClick={() => toggleSort('days_held')}>
                    Days {sortBy === 'days_held' ? (sortDesc ? '↓' : '↑') : ''}
                  </TableColumnHeader>
                  <TableColumnHeader>Date</TableColumnHeader>
                  <TableColumnHeader textAlign="end">Shares</TableColumnHeader>
                  <TableColumnHeader textAlign="end">Cost/Sh</TableColumnHeader>
                  <TableColumnHeader textAlign="end">Cost Basis</TableColumnHeader>
                  <TableColumnHeader cursor="pointer" textAlign="end" onClick={() => toggleSort('market_value')}>
                    Value {sortBy === 'market_value' ? (sortDesc ? '↓' : '↑') : ''}
                  </TableColumnHeader>
                  <TableColumnHeader cursor="pointer" textAlign="end" onClick={() => toggleSort('unrealized_pnl')}>
                    P/L {sortBy === 'unrealized_pnl' ? (sortDesc ? '↓' : '↑') : ''}
                  </TableColumnHeader>
                  <TableColumnHeader textAlign="end">P/L %</TableColumnHeader>
                  <TableColumnHeader>Source</TableColumnHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLots.map((l) => {
                  const daysToLT = Math.max(0, 365 - l.days_held);
                  return (
                    <TableRow key={l.id} bg={l.approaching_lt ? 'yellow.950' : undefined}>
                      <TableCell>
                        <Text fontFamily="mono" fontWeight="semibold">{l.symbol}</Text>
                      </TableCell>
                      <TableCell>
                        <Badge size="sm" colorPalette={l.is_long_term ? 'green' : l.approaching_lt ? 'yellow' : 'gray'}>
                          {l.is_long_term ? 'LT' : 'ST'}
                        </Badge>
                      </TableCell>
                      <TableCell textAlign="end">
                        <Text fontSize="xs" color={l.approaching_lt ? 'yellow.400' : 'fg.muted'}>
                          {l.days_held}d
                          {l.approaching_lt && <Text as="span" fontSize="xs" color="yellow.400"> ({daysToLT}d to LT)</Text>}
                        </Text>
                      </TableCell>
                      <TableCell>{fmtDate(l.purchase_date)}</TableCell>
                      <TableCell textAlign="end">{l.shares.toLocaleString()}</TableCell>
                      <TableCell textAlign="end">{formatMoney(l.cost_per_share, currency)}</TableCell>
                      <TableCell textAlign="end">{l.cost_basis != null ? formatMoney(l.cost_basis, currency, { maximumFractionDigits: 0 }) : '—'}</TableCell>
                      <TableCell textAlign="end">{formatMoney(l.market_value, currency, { maximumFractionDigits: 0 })}</TableCell>
                      <TableCell textAlign="end" color={l.unrealized_pnl >= 0 ? 'fg.success' : 'fg.error'}>
                        {formatMoney(l.unrealized_pnl, currency, { maximumFractionDigits: 0 })}
                      </TableCell>
                      <TableCell textAlign="end" color={l.unrealized_pnl_pct >= 0 ? 'fg.success' : 'fg.error'}>
                        {l.unrealized_pnl_pct.toFixed(1)}%
                      </TableCell>
                      <TableCell>
                        {l.source && (
                          <Badge size="sm" variant="outline" colorPalette={l.source === 'official_statement' ? 'blue' : 'gray'}>
                            {l.source === 'official_statement' ? 'Official' : 'Estimated'}
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </TableRoot>
          </TableScrollArea>
        </CardBody>
      </CardRoot>
      )}
    </VStack>
  );
};

export default PortfolioTaxCenter;
