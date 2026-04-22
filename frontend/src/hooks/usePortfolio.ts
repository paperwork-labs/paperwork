import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, {
  portfolioApi,
  tasksApi,
  handleApiError,
  PortfolioSummary,
  accountsApi,
  optionsApi,
  activityApi,
  unwrapResponse,
  unwrapResponseSingle,
  type PnlSummaryData,
  type PortfolioNarrativePayload,
  type PortfolioNarrativePendingPayload,
} from '../services/api';
import type { EnrichedPosition } from '../types/portfolio';
import toast from 'react-hot-toast';

export const usePortfolio = () => {
  return useQuery({
    queryKey: ['livePortfolio'],
    queryFn: async () => {
      const result = await portfolioApi.getLive();
      return result.data;
    },
    refetchInterval: 30000,
    staleTime: 20000,
  });
};

export const usePositions = (accountId?: string) => {
  return useQuery<EnrichedPosition[]>({
    queryKey: ['portfolioStocks', accountId],
    queryFn: async () => {
      const r = await portfolioApi.getStocks(accountId);
      return unwrapResponse<EnrichedPosition>(r, 'stocks');
    },
    staleTime: 60000,
  });
};

export const useOptions = (accountId?: string) => {
  const portfolio = useQuery({
    queryKey: ['portfolioOptions', accountId],
    queryFn: () => optionsApi.getPortfolio(accountId),
    staleTime: 60000,
  });
  const summary = useQuery({
    queryKey: ['portfolioOptionsSummary', accountId],
    queryFn: () => optionsApi.getSummary(accountId),
    staleTime: 60000,
  });
  return {
    portfolio,
    summary,
    data: (portfolio.data as any)?.data,
    summaryData: summary.data,
    isPending: portfolio.isPending || summary.isPending,
    isError: portfolio.isError || summary.isError,
    error: portfolio.error || summary.error,
  };
};

export interface UseActivityParams {
  accountId?: string;
  start?: string;
  end?: string;
  symbol?: string;
  category?: string;
  side?: string;
  limit?: number;
  offset?: number;
}

export const useActivity = (params: UseActivityParams = {}) => {
  return useQuery({
    queryKey: ['portfolioActivity', params],
    queryFn: () => activityApi.getActivity(params),
    staleTime: 30000,
  });
};

export const useDividends = (accountId?: string, days: number = 365) => {
  return useQuery({
    queryKey: ['portfolioDividends', accountId, days],
    queryFn: async () => {
      const r = await portfolioApi.getDividends(accountId, days);
      return unwrapResponse(r, 'dividends');
    },
    staleTime: 60000,
  });
};

export const useCategoryViews = () => {
  return useQuery({
    queryKey: ['portfolioCategoryViews'],
    queryFn: async () => {
      const r = await portfolioApi.getCategoryViews();
      return unwrapResponse(r, 'views') as { key: string; label: string }[];
    },
    staleTime: 120000,
  });
};

export const useCategories = (categoryType?: string) => {
  return useQuery({
    queryKey: ['portfolioCategories', categoryType ?? 'all'],
    queryFn: async () => {
      const r = await portfolioApi.getCategories(categoryType);
      const raw = r as Record<string, any> | undefined;
      const nested = raw?.data?.data ?? raw?.data ?? raw;
      return {
        categories: (nested?.categories ?? []) as any[],
        uncategorized: (nested?.uncategorized ?? { positions_count: 0, total_value: 0, actual_allocation_pct: 0, position_ids: [] }) as {
          positions_count: number;
          total_value: number;
          actual_allocation_pct: number;
          position_ids: number[];
        },
      };
    },
    staleTime: 60000,
  });
};

export const useCategoryPositions = () => {
  return useQuery({
    queryKey: ['portfolioStocksForCategories'],
    queryFn: async () => {
      const r = await portfolioApi.getStocks(undefined, false);
      return unwrapResponse<{ id: number; symbol: string; market_value?: number }>(r, 'stocks');
    },
    staleTime: 60000,
  });
};

export interface PortfolioInsightsData {
  harvest_candidates: Array<{ symbol: string; unrealized_pnl: number; shares: number; days_held: number }>;
  approaching_lt: Array<{ symbol: string; days_held: number; days_to_lt: number; shares: number; unrealized_pnl: number }>;
  concentration_warnings: Array<{ symbol: string; market_value: number; pct_of_portfolio: number }>;
  total_positions?: number;
  total_tax_lots?: number;
}

export const usePortfolioInsights = () => {
  return useQuery({
    queryKey: ['portfolioInsights'],
    queryFn: async () => {
      try {
        const r = await portfolioApi.getInsights();
        const raw = r as Record<string, any> | undefined;
        const data = raw?.data?.data ?? raw?.data ?? raw;
        return (data ?? null) as PortfolioInsightsData | null;
      } catch {
        return null;
      }
    },
    staleTime: 300000,
  });
};

export const usePortfolioOverview = (accountId?: string) => {
  const summary = usePortfolioSummary(accountId);
  const accounts = usePortfolioAccounts();
  return {
    summary,
    accounts,
    data: summary.data,
    accountsData: accounts.data,
    isPending: summary.isPending || accounts.isPending,
    isError: summary.isError || accounts.isError,
    error: summary.error || accounts.error,
  };
};

export const usePortfolioPerformanceHistory = (params: { accountId?: string; period?: string } = {}) => {
  return useQuery<Array<{ date: string; total_value: number }>>({
    queryKey: ['portfolioPerformanceHistory', params.accountId, params.period],
    queryFn: async () => {
      const r = await portfolioApi.getPerformanceHistory(params);
      return unwrapResponse<{ date: string; total_value: number }>(r, 'series');
    },
    staleTime: 60000,
  });
};

export const usePortfolioSummary = (accountId?: string) => {
  return useQuery({
    queryKey: ['portfolioSummary', accountId],
    queryFn: () => portfolioApi.getDashboard(accountId),
    refetchInterval: 30000,
    staleTime: 20000,
  });
};

export const usePortfolioHealth = () => {
  return useQuery({
    queryKey: ['portfolioHealth'],
    queryFn: () => portfolioApi.getDashboard(),
    refetchInterval: 60000,
    staleTime: 30000,
  });
};

export const usePortfolioAccounts = () => {
  return useQuery({
    queryKey: ['portfolioAccounts'],
    queryFn: accountsApi.list,
    staleTime: 300000,
  });
};

export const usePortfolioSync = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: portfolioApi.sync,
    onMutate: () => {
      toast.loading('Syncing portfolio data...', { id: 'portfolio-sync' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioSummary'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioHealth'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioStocks'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioOptions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioOptionsSummary'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioActivity'] });
      queryClient.invalidateQueries({ queryKey: ['livePortfolio'] });
      toast.success('Portfolio data synced successfully', { id: 'portfolio-sync' });
    },
    onError: (error: any) => {
      const message = handleApiError(error);
      toast.error(`Sync failed: ${message}`, { id: 'portfolio-sync' });
    },
  });
};

export const usePortfolioDigest = () => {
  return useMutation({
    mutationFn: tasksApi.sendPortfolioDigest,
    onMutate: () => {
      toast.loading('Sending portfolio digest...', { id: 'portfolio-digest' });
    },
    onSuccess: () => {
      toast.success('Portfolio digest sent to Discord', { id: 'portfolio-digest' });
    },
    onError: (error: any) => {
      const message = handleApiError(error);
      toast.error(`Failed to send digest: ${message}`, { id: 'portfolio-digest' });
    },
  });
};

export const usePortfolioAlerts = () => {
  return useMutation({
    mutationFn: tasksApi.forcePortfolioAlerts,
    onMutate: () => {
      toast.loading('Generating portfolio alerts...', { id: 'portfolio-alerts' });
    },
    onSuccess: (data: any) => {
      toast.success(`Generated ${data.alerts_generated || 0} portfolio alerts`, { id: 'portfolio-alerts' });
    },
    onError: (error: any) => {
      const message = handleApiError(error);
      toast.error(`Failed to generate alerts: ${message}`, { id: 'portfolio-alerts' });
    },
  });
};

export const useSignals = () => {
  return useMutation({
    mutationFn: tasksApi.sendSignals,
    onMutate: () => {
      toast.loading('Generating trading signals...', { id: 'signals' });
    },
    onSuccess: () => {
      toast.success('Trading signals sent to Discord', { id: 'signals' });
    },
    onError: (error: any) => {
      const message = handleApiError(error);
      toast.error(`Failed to send signals: ${message}`, { id: 'signals' });
    },
  });
};

export const useMorningBrew = () => {
  return useMutation({
    mutationFn: tasksApi.sendMorningBrew,
    onMutate: () => {
      toast.loading('Preparing morning brew...', { id: 'morning-brew' });
    },
    onSuccess: () => {
      toast.success('Morning brew sent to Discord', { id: 'morning-brew' });
    },
    onError: (error: any) => {
      const message = handleApiError(error);
      toast.error(`Failed to send morning brew: ${message}`, { id: 'morning-brew' });
    },
  });
};

export const useSystemStatus = () => {
  return useMutation({
    mutationFn: tasksApi.sendSystemStatus,
    onMutate: () => {
      toast.loading('Checking system status...', { id: 'system-status' });
    },
    onSuccess: () => {
      toast.success('System status sent to Discord', { id: 'system-status' });
    },
    onError: (error: any) => {
      const message = handleApiError(error);
      toast.error(`System status check failed: ${message}`, { id: 'system-status' });
    },
  });
};

export const useDashboardData = () => {
  const portfolioSummary = usePortfolioSummary();
  const portfolioHealth = usePortfolioHealth();
  const portfolioAccounts = usePortfolioAccounts();

  return {
    portfolio: portfolioSummary,
    health: portfolioHealth,
    accounts: portfolioAccounts,
    isPending: portfolioSummary.isPending || portfolioHealth.isPending,
    isError: portfolioSummary.isError || portfolioHealth.isError,
    error: portfolioSummary.error || portfolioHealth.error,
  };
};

export const useAccountBalances = (accountId?: number) => {
  return useQuery({
    queryKey: ['portfolio-balances', accountId],
    queryFn: async () => {
      const r = await portfolioApi.getBalances(accountId);
      return (r as any)?.data?.data?.balances ?? (r as any)?.data?.balances ?? [];
    },
    staleTime: 60_000,
  });
};

export const useMarginInterest = (accountId?: number, period?: string) => {
  return useQuery({
    queryKey: ['portfolio-margin-interest', accountId, period],
    queryFn: async () => {
      const r = await portfolioApi.getMarginInterest(accountId, period);
      return (r as any)?.data?.data?.margin_interest ?? (r as any)?.data?.margin_interest ?? [];
    },
    staleTime: 120_000,
  });
};

export const useRealizedGains = (year?: number, accountId?: string) => {
  return useQuery({
    queryKey: ['portfolio-realized-gains', year, accountId],
    queryFn: async () => {
      const r = await portfolioApi.getRealizedGains(year, accountId);
      return (r as any)?.data?.data ?? (r as any)?.data ?? {};
    },
    staleTime: 300_000,
  });
};

export interface OpenOptionsTaxItem {
  id: number;
  symbol: string;
  option_type: string;
  open_quantity: number;
  multiplier: string;
  cost_basis: string | null;
  mark: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_pct: string | null;
  days_to_expiry: number | null;
  tax_holding_class: 'short_term' | 'long_term' | null;
  opened_at: string | null;
}

export interface OpenOptionsTaxSummaryData {
  items: OpenOptionsTaxItem[];
  total_unrealized_pnl: string | null;
  counts: { longs: number; shorts: number };
}

export const useOpenOptionsTaxSummary = () => {
  return useQuery({
    queryKey: ['portfolio-open-options-tax-summary'],
    queryFn: async (): Promise<OpenOptionsTaxSummaryData> => {
      const r = await api.get<{ status: string; data: OpenOptionsTaxSummaryData }>('/portfolio/options/tax-summary');
      const body = r.data;
      if (body?.status !== 'success' || body.data == null) {
        throw new Error('Unexpected open options tax summary response');
      }
      return body.data;
    },
    staleTime: 60_000,
  });
};

export const useClosedPositions = (accountId?: string) => {
  return useQuery({
    queryKey: ['portfolio-closed-positions', accountId],
    queryFn: async () => {
      const r = await portfolioApi.getClosedPositions(accountId);
      return (r as any)?.data?.data?.closed_positions ?? (r as any)?.data?.closed_positions ?? [];
    },
    staleTime: 300_000,
  });
};

export const useDividendSummary = (accountId?: string) => {
  return useQuery({
    queryKey: ['portfolio-dividend-summary', accountId],
    queryFn: async () => {
      const r = await portfolioApi.getDividendSummary(accountId);
      return (r as any)?.data?.data ?? (r as any)?.data ?? {};
    },
    staleTime: 300_000,
  });
};

const PNL_SUMMARY_QUERY_DEFAULTS: PnlSummaryData = {
  unrealized_pnl: 0,
  realized_pnl: 0,
  total_dividends: 0,
  total_fees: 0,
  total_return: 0,
};

export const usePnlSummary = (accountId?: string) => {
  return useQuery<PnlSummaryData>({
    queryKey: ['portfolio-pnl-summary', accountId],
    queryFn: async () => {
      const r = await portfolioApi.getPnlSummary(accountId);
      return r ?? PNL_SUMMARY_QUERY_DEFAULTS;
    },
    staleTime: 60_000,
  });
};

export const useLiveSummary = (accountId?: string) => {
  return useQuery({
    queryKey: ['portfolio-live-summary', accountId],
    queryFn: async () => {
      try {
        const r = await portfolioApi.getLiveSummary(accountId);
        return (r as any)?.data?.data ?? (r as any)?.data ?? {};
      } catch {
        return { is_live: false };
      }
    },
    staleTime: 60_000,
    retry: 1,
  });
};

export const useRiskMetrics = () => {
  return useQuery({
    queryKey: ['portfolio-risk-metrics'],
    queryFn: async () => {
      const r = await portfolioApi.getRiskMetrics();
      return (r as any) ?? {};
    },
    staleTime: 300_000,
  });
};

export const useRebalanceSuggestions = () => {
  return useQuery({
    queryKey: ['portfolio-rebalance-suggestions'],
    queryFn: async () => {
      const r = await portfolioApi.getRebalanceSuggestions();
      return (r as any)?.data?.data ?? (r as any)?.data ?? {};
    },
    staleTime: 300_000,
  });
};

export const usePortfolioNarrativeLatest = () => {
  return useQuery({
    queryKey: ['portfolio-narrative-latest'],
    queryFn: async (): Promise<PortfolioNarrativePayload | null> => {
      const raw = await portfolioApi.getNarrativeLatest();
      if (
        raw &&
        typeof raw === 'object' &&
        'status' in raw &&
        (raw as PortfolioNarrativePendingPayload).status === 'pending'
      ) {
        return null;
      }
      return raw as PortfolioNarrativePayload;
    },
    staleTime: 300_000,
    retry: false,
  });
};

type SummaryWithPositions = PortfolioSummary & { all_positions?: unknown[]; positions?: unknown[] };
interface ChartPosition {
  symbol: string;
  market_value?: number;
  value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  account?: string;
}
export const transformPortfolioDataForCharts = (data: PortfolioSummary) => {
  const withPos = data as SummaryWithPositions;
  const positions = withPos?.all_positions ?? withPos?.positions ?? [];
  return (Array.isArray(positions) ? positions : []).map((position: unknown) => {
    const p = position as ChartPosition;
    return {
      symbol: p.symbol,
      value: p.market_value ?? p.value ?? 0,
      gainLoss: p.unrealized_pnl ?? 0,
      gainLossPct: p.unrealized_pnl_pct ?? 0,
      account: p.account,
    };
  });
};
