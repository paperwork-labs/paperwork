import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

export interface PortfolioSymbolData {
  symbol: string;
  quantity: number;
  cost_basis: number;
  market_value: number;
  unrealized_pnl: number;
}

export function usePortfolioSymbols() {
  return useQuery<Record<string, PortfolioSymbolData>>({
    queryKey: ['portfolioSymbols'],
    queryFn: async () => {
      const res = await api.get('/portfolio/symbols');
      return res.data?.data ?? {};
    },
    staleTime: 120_000,
    enabled: true,
  });
}
