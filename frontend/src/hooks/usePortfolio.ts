import { useQuery, useMutation, useQueryClient } from 'react-query';
import {
  portfolioApi,
  tasksApi,
  handleApiError,
  PortfolioSummary,
  accountsApi,
  optionsApi,
  activityApi,
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
      const raw = (r as { data?: { data?: { stocks?: unknown[] }; stocks?: unknown[] }; stocks?: unknown[] });
      const stocks = raw?.data?.data?.stocks ?? raw?.data?.stocks ?? raw?.stocks ?? [];
      return stocks as EnrichedPosition[];
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
    () => portfolioApi.getDividends(accountId, days),
    {
      staleTime: 60000,
      onError: (error) => {
        const message = handleApiError(error);
        toast.error(`Dividends: ${message}`);
      },
    }
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
      const raw = r as { data?: { data?: { series?: unknown[] }; series?: unknown[] }; series?: unknown[] };
      return (raw?.data?.data?.series ?? raw?.data?.series ?? raw?.series ?? []) as Array<{ date: string; total_value: number }>;
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

// Helper function to transform API data for charts
export const transformPortfolioDataForCharts = (data: PortfolioSummary) => {
  const anyData: any = data as any;
  const positions = anyData?.all_positions || anyData?.positions || [];
  return positions.map((position: any) => ({
    symbol: position.symbol,
    value: position.market_value ?? position.value ?? 0,
    gainLoss: position.unrealized_pnl ?? 0,
    gainLossPct: position.unrealized_pnl_pct ?? 0,
    account: position.account,
  }));
}; 