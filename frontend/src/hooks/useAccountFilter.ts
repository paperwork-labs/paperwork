import { useMemo } from 'react';
import { useAccountContext } from '../context/AccountContext';

export interface AccountData {
  account_id: string;
  account_name: string;
  account_type: string;
  broker: string;
  total_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct?: number;
  positions_count: number;
  allocation_pct: number;
  available_funds?: number;
  buying_power?: number;
  day_change?: number;
  day_change_pct?: number;
}

export interface FilterableItem {
  account?: string;
  account_id?: string;
  account_number?: string; // Add support for options data
  brokerage?: string;
  broker?: string;
  [key: string]: any;
}

export interface AccountFilterConfig {
  showAllOption?: boolean;
  defaultSelection?: string;
  filterByBrokerage?: boolean; // Whether to filter by brokerage name vs account ID
  size?: 'sm' | 'md' | 'lg';
  variant?: 'simple' | 'detailed';
  showSummary?: boolean;
}

export interface AccountFilterState {
  selectedAccount: string;
  setSelectedAccount: (accountId: string) => void;
  filteredData: FilterableItem[];
  accounts: AccountData[];
  totalValue: number;
  totalPnL: number;
  totalPositions: number;
  isLoading: boolean;
  error: string | null;
}

/**
 * Unified account filtering hook for consistent filtering across all pages
 * 
 * @param data - Array of items to filter (holdings, transactions, etc.)
 * @param accounts - Array of account data for the selector
 * @param config - Configuration options for the filter
 * @returns Filtered data and account selection state
 */
export const useAccountFilter = <T extends FilterableItem>(
  data: T[],
  accounts: AccountData[] = [],
  config: AccountFilterConfig = {}
): AccountFilterState => {
  const {
    showAllOption = true,
    defaultSelection = 'all',
    filterByBrokerage = false,
    size = 'md',
    variant = 'detailed',
    showSummary = true
  } = config;

  const { selected: globalSelected, setSelected: setGlobalSelected } = useAccountContext();
  const selectedAccount = globalSelected || 'all';
  const setSelectedAccount = setGlobalSelected;
  const isLoading = false;
  const error: string | null = null;

  const filteredData = useMemo(() => {
    if (!data?.length) return [];

    if (selectedAccount === 'all') {
      return data;
    }

    // Category filters using provided accounts metadata.
    // HSA is split out of "taxable" so HSA dollars don't leak into a
    // taxable-brokerage view — they belong to a tax-advantaged bucket that
    // just happens not to be a retirement account. (Founder pain #2.)
    const selectedLower = selectedAccount.toLowerCase();
    if (selectedLower === 'taxable' || selectedLower === 'ira' || selectedLower === 'hsa') {
      const allowedIds = new Set(
        accounts
          .filter((acc) => {
            const t = (acc.account_type || '').toLowerCase();
            const isIra = t.includes('ira') || t.includes('retire') || t.includes('401');
            const isHsa = t.includes('hsa') || t.includes('health_savings');
            if (selectedLower === 'ira') return isIra;
            if (selectedLower === 'hsa') return isHsa;
            // taxable: everything that is neither retirement nor HSA
            return !isIra && !isHsa;
          })
          .map((acc) => acc.account_id)
      );
      return data.filter((item) => {
        const id = (item.account || item.account_id || item.account_number) as string | undefined;
        return id ? allowedIds.has(id) : false;
      });
    }

    return data.filter(item => {
      if (filterByBrokerage) {
        // Filter by brokerage name (IBKR, TASTYTRADE, etc.)
        return (
          item.brokerage?.toLowerCase() === selectedAccount.toLowerCase() ||
          item.broker?.toLowerCase() === selectedAccount.toLowerCase()
        );
      } else {
        // Filter by specific account ID (e.g., IBKR_ACCOUNT)
        return (
          item.account === selectedAccount ||
          item.account_id === selectedAccount ||
          item.account_number === selectedAccount
        );
      }
    });
  }, [data, selectedAccount, filterByBrokerage, accounts]);

  // Calculate aggregate metrics
  const { totalValue, totalPnL, totalPositions } = useMemo(() => {
    if (selectedAccount === 'all') {
      return {
        totalValue: accounts.reduce((sum, acc) => sum + acc.total_value, 0),
        totalPnL: accounts.reduce((sum, acc) => sum + acc.unrealized_pnl, 0),
        totalPositions: accounts.reduce((sum, acc) => sum + acc.positions_count, 0),
      };
    } else {
      const selectedAccountData = accounts.find(acc => acc.account_id === selectedAccount);
      return {
        totalValue: selectedAccountData?.total_value || 0,
        totalPnL: selectedAccountData?.unrealized_pnl || 0,
        totalPositions: selectedAccountData?.positions_count || 0,
      };
    }
  }, [accounts, selectedAccount]);

  return {
    selectedAccount,
    setSelectedAccount,
    filteredData,
    accounts,
    totalValue,
    totalPnL,
    totalPositions,
    isLoading,
    error,
  };
};

/**
 * Helper function to transform portfolio data into AccountData format
 * for use with the account filter
 */
export const transformPortfolioToAccounts = (portfolioData: any): AccountData[] => {
  if (!portfolioData?.accounts) return [];

  return Object.entries(portfolioData.accounts).map(([accountId, accountData]: [string, any]) => ({
    account_id: accountId,
    account_name: accountData.account_summary?.account_name || `Account ${accountId}`,
    account_type: accountData.account_summary?.account_type || 'taxable',
    broker: accountData.account_summary?.broker || 'IBKR',
    total_value: accountData.account_summary?.net_liquidation || 0,
    unrealized_pnl: accountData.account_summary?.unrealized_pnl || 0,
    unrealized_pnl_pct: accountData.account_summary?.unrealized_pnl_pct || 0,
    positions_count: accountData.all_positions?.length || 0,
    allocation_pct: 0, // Calculate this based on total portfolio
    available_funds: accountData.account_summary?.available_funds,
    buying_power: accountData.account_summary?.buying_power,
    day_change: accountData.account_summary?.day_change,
    day_change_pct: accountData.account_summary?.day_change_pct,
  }));
};

/**
 * Helper function to get formatted account display name
 */
export const getAccountDisplayName = (account: AccountData): string => {
  const value = account.total_value;
  const pnlPct = account.unrealized_pnl_pct ?? 0;
  const formattedValue = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

  const formattedPnL = `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`;

  return `${account.account_name} • ${formattedValue} • ${formattedPnL}`;
};

export default useAccountFilter; 