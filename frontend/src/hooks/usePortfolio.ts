import { useQuery, useMutation, useQueryClient } from 'react-query';
import {
  portfolioApi,
  tasksApi,
  handleApiError,
  PortfolioSummary,
  accountsApi,
  optionsApi,
  activityApi,
  unwrapResponse,
  unwrapResponseSingle,
} from '../services/api';
import type { EnrichedPosition } from '../types/portfolio';
import toast from 'react-hot-toast';

// Main hook for live portfolio data (used by most components). Backward compat: thin wrapper.
export const usePortfolio = () => {
  return useQuery(
    'livePortfolio',
    async () => {
      const result = await portfolioApi.getLive();
      return result.data;
    },
    {
      refetchInterval: 30000,
      staleTime: 20000,
      onError: (error) => {
        console.error('Portfolio data fetch failed:', error);
        toast.error('Failed to load portfolio data');
      },
    }
  );
};

// Enriched stock positions with market data (stage, RS, etc.). For Holdings page.
export const usePositions = (accountId?: string) => {
  return useQuery<EnrichedPosition[]>(
    ['portfolioStocks', accountId],
    async () => {
      const r = await portfolioApi.getStocks(accountId);
      return unwrapResponse<EnrichedPosition>(r, 'stocks');
    },
    {
      staleTime: 60000,
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Holdings: ${message}`);
      },
    }
  );
};

// Options positions and summary. For Options page.
export const useOptions = (accountId?: string) => {
  const portfolio = useQuery(
    ['portfolioOptions', accountId],
    () => optionsApi.getPortfolio(accountId),
    { staleTime: 60000 }
  );
  const summary = useQuery(
    ['portfolioOptionsSummary', accountId],
    () => optionsApi.getSummary(accountId),
    { staleTime: 60000 }
  );
  return {
    portfolio,
    summary,
    data: portfolio.data?.data,
    summaryData: summary.data,
    isLoading: portfolio.isLoading || summary.isLoading,
    isError: portfolio.isError || summary.isError,
    error: portfolio.error || summary.error,
  };
};

// Unified activity feed. For Transactions page.
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
  return useQuery(
    ['portfolioActivity', params],
    () => activityApi.getActivity(params),
    {
      staleTime: 30000,
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Activity: ${message}`);
      },
    }
  );
};

// Dividend history. For Transactions or dedicated view.
export const useDividends = (accountId?: string, days: number = 365) => {
  return useQuery(
    ['portfolioDividends', accountId, days],
    async () => {
      const r = await portfolioApi.getDividends(accountId, days);
      return unwrapResponse(r, 'dividends');
    },
    {
      staleTime: 60000,
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Dividends: ${message}`);
      },
    }
  );
};

// Categories with allocation data. For Categories page.
export const useCategories = () => {
  return useQuery(
    'portfolioCategories',
    async () => {
      const r = await portfolioApi.getCategories();
      return unwrapResponse(r, 'categories');
    },
    {
      staleTime: 60000,
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Categories: ${message}`);
      },
    }
  );
};

// Positions for category assignment (no enrichment needed).
export const useCategoryPositions = () => {
  return useQuery(
    'portfolioStocksForCategories',
    async () => {
      const r = await portfolioApi.getStocks(undefined, false);
      return unwrapResponse<{ id: number; symbol: string; market_value?: number }>(r, 'stocks');
    },
    { staleTime: 60000 }
  );
};

export interface PortfolioInsightsData {
  harvest_candidates: Array<{ symbol: string; unrealized_pnl: number; shares: number; days_held: number }>;
  approaching_lt: Array<{ symbol: string; days_held: number; days_to_lt: number; shares: number; unrealized_pnl: number }>;
  concentration_warnings: Array<{ symbol: string; market_value: number; pct_of_portfolio: number }>;
  total_positions?: number;
  total_tax_lots?: number;
}

export const usePortfolioInsights = () => {
  return useQuery(
    'portfolioInsights',
    async () => {
      try {
        const r = await portfolioApi.getInsights();
        const raw = r as Record<string, any> | undefined;
        const data = raw?.data?.data ?? raw?.data ?? raw;
        return (data ?? null) as PortfolioInsightsData | null;
      } catch {
        return null;
      }
    },
    { staleTime: 300000 }
  );
};

// Overview page: dashboard summary + accounts. Performance/analytics added when APIs exist.
export const usePortfolioOverview = (accountId?: string) => {
  const summary = usePortfolioSummary(accountId);
  const accounts = usePortfolioAccounts();
  return {
    summary,
    accounts,
    data: summary.data,
    accountsData: accounts.data,
    isLoading: summary.isLoading || accounts.isLoading,
    isError: summary.isError || accounts.isError,
    error: summary.error || accounts.error,
  };
};

// Portfolio value over time for performance chart.
export const usePortfolioPerformanceHistory = (params: { accountId?: string; period?: string } = {}) => {
  return useQuery<Array<{ date: string; total_value: number }>>(
    ['portfolioPerformanceHistory', params.accountId, params.period],
    async () => {
      const r = await portfolioApi.getPerformanceHistory(params);
      return unwrapResponse<{ date: string; total_value: number }>(r, 'series');
    },
    { staleTime: 60000 }
  );
};

// Hook for portfolio summary data
export const usePortfolioSummary = (accountId?: string) => {
  return useQuery(
    ['portfolioSummary', accountId],
    () => portfolioApi.getDashboard(accountId),
    {
      refetchInterval: 30000, // Refetch every 30 seconds
      staleTime: 20000, // Consider data stale after 20 seconds
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Portfolio Error: ${message}`);
      },
    }
  );
};

// Hook for portfolio health check
export const usePortfolioHealth = () => {
  return useQuery(
    'portfolioHealth',
    () => portfolioApi.getDashboard(),
    {
      refetchInterval: 60000, // Check every minute
      staleTime: 30000,
      onError: (error) => {
        const message = handleApiError(error);
        console.error('Portfolio health check failed:', message);
      },
    }
  );
};

// Hook for portfolio accounts
export const usePortfolioAccounts = () => {
  return useQuery(
    'portfolioAccounts',
    accountsApi.list,
    {
      staleTime: 300000, // 5 minutes
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Accounts Error: ${message}`);
      },
    }
  );
};

// Hook for syncing portfolio data
export const usePortfolioSync = () => {
  const queryClient = useQueryClient();

  return useMutation(
    portfolioApi.sync,
    {
      onMutate: () => {
        toast.loading('Syncing portfolio data...', { id: 'portfolio-sync' });
      },
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioSummary');
        queryClient.invalidateQueries('portfolioHealth');
        queryClient.invalidateQueries('portfolioStocks');
        queryClient.invalidateQueries('portfolioOptions');
        queryClient.invalidateQueries('portfolioOptionsSummary');
        queryClient.invalidateQueries('portfolioActivity');
        queryClient.invalidateQueries('livePortfolio');
        toast.success('Portfolio data synced successfully', { id: 'portfolio-sync' });
      },
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Sync failed: ${message}`, { id: 'portfolio-sync' });
      },
    }
  );
};

// Hook for sending portfolio digest
export const usePortfolioDigest = () => {
  return useMutation(
    tasksApi.sendPortfolioDigest,
    {
      onMutate: () => {
        toast.loading('Sending portfolio digest...', { id: 'portfolio-digest' });
      },
      onSuccess: (data) => {
        toast.success('Portfolio digest sent to Discord', { id: 'portfolio-digest' });
      },
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Failed to send digest: ${message}`, { id: 'portfolio-digest' });
      },
    }
  );
};

// Hook for forcing portfolio alerts
export const usePortfolioAlerts = () => {
  return useMutation(
    tasksApi.forcePortfolioAlerts,
    {
      onMutate: () => {
        toast.loading('Generating portfolio alerts...', { id: 'portfolio-alerts' });
      },
      onSuccess: (data) => {
        toast.success(`Generated ${data.alerts_generated || 0} portfolio alerts`, { id: 'portfolio-alerts' });
      },
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Failed to generate alerts: ${message}`, { id: 'portfolio-alerts' });
      },
    }
  );
};

// Hook for sending signals
export const useSignals = () => {
  return useMutation(
    tasksApi.sendSignals,
    {
      onMutate: () => {
        toast.loading('Generating trading signals...', { id: 'signals' });
      },
      onSuccess: (data) => {
        toast.success('Trading signals sent to Discord', { id: 'signals' });
      },
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Failed to send signals: ${message}`, { id: 'signals' });
      },
    }
  );
};

// Hook for sending morning brew
export const useMorningBrew = () => {
  return useMutation(
    tasksApi.sendMorningBrew,
    {
      onMutate: () => {
        toast.loading('Preparing morning brew...', { id: 'morning-brew' });
      },
      onSuccess: (data) => {
        toast.success('Morning brew sent to Discord', { id: 'morning-brew' });
      },
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Failed to send morning brew: ${message}`, { id: 'morning-brew' });
      },
    }
  );
};

// Hook for system status
export const useSystemStatus = () => {
  return useMutation(
    tasksApi.sendSystemStatus,
    {
      onMutate: () => {
        toast.loading('Checking system status...', { id: 'system-status' });
      },
      onSuccess: (data) => {
        toast.success('System status sent to Discord', { id: 'system-status' });
      },
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`System status check failed: ${message}`, { id: 'system-status' });
      },
    }
  );
};

// Combined hook for dashboard data
export const useDashboardData = () => {
  const portfolioSummary = usePortfolioSummary();
  const portfolioHealth = usePortfolioHealth();
  const portfolioAccounts = usePortfolioAccounts();

  return {
    portfolio: portfolioSummary,
    health: portfolioHealth,
    accounts: portfolioAccounts,
    isLoading: portfolioSummary.isLoading || portfolioHealth.isLoading,
    isError: portfolioSummary.isError || portfolioHealth.isError,
    error: portfolioSummary.error || portfolioHealth.error,
  };
};

// Account balances (cash, margin, buying power, etc.)
export const useAccountBalances = (accountId?: number) => {
  return useQuery(
    ['portfolio-balances', accountId],
    async () => {
      const r = await portfolioApi.getBalances(accountId);
      return (r as any)?.data?.data?.balances ?? (r as any)?.data?.balances ?? [];
    },
    { staleTime: 60_000 }
  );
};

// Margin interest accruals
export const useMarginInterest = (accountId?: number, period?: string) => {
  return useQuery(
    ['portfolio-margin-interest', accountId, period],
    async () => {
      const r = await portfolioApi.getMarginInterest(accountId, period);
      return (r as any)?.data?.data?.margin_interest ?? (r as any)?.data?.margin_interest ?? [];
    },
    { staleTime: 120_000 }
  );
};

export const useRealizedGains = (year?: number, accountId?: string) => {
  return useQuery(
    ['portfolio-realized-gains', year, accountId],
    async () => {
      const r = await portfolioApi.getRealizedGains(year, accountId);
      return (r as any)?.data?.data ?? (r as any)?.data ?? {};
    },
    { staleTime: 300_000 }
  );
};

export const useClosedPositions = (accountId?: string) => {
  return useQuery(
    ['portfolio-closed-positions', accountId],
    async () => {
      const r = await portfolioApi.getClosedPositions(accountId);
      return (r as any)?.data?.data?.closed_positions ?? (r as any)?.data?.closed_positions ?? [];
    },
    { staleTime: 300_000 }
  );
};

export const useDividendSummary = (accountId?: string) => {
  return useQuery(
    ['portfolio-dividend-summary', accountId],
    async () => {
      const r = await portfolioApi.getDividendSummary(accountId);
      return (r as any)?.data?.data ?? (r as any)?.data ?? {};
    },
    { staleTime: 300_000 }
  );
};

export const useLiveSummary = () => {
  return useQuery(
    ['portfolio-live-summary'],
    async () => {
      const r = await portfolioApi.getLiveSummary();
      return (r as any)?.data?.data ?? (r as any)?.data ?? {};
    },
    { staleTime: 60_000, retry: 1 }
  );
};

export const useRiskMetrics = () => {
  return useQuery(
    ['portfolio-risk-metrics'],
    async () => {
      const r = await portfolioApi.getRiskMetrics();
      return (r as any) ?? {};
    },
    { staleTime: 300_000 }
  );
};

export const useRebalanceSuggestions = () => {
  return useQuery(
    ['portfolio-rebalance-suggestions'],
    async () => {
      const r = await portfolioApi.getRebalanceSuggestions();
      return (r as any)?.data?.data ?? (r as any)?.data ?? {};
    },
    { staleTime: 300_000 }
  );
};

// Helper function to transform API data for charts
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