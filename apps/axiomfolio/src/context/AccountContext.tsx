import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useUser } from '@clerk/nextjs';

import api from '../services/api';

// Bucket categories expose fast "all my taxable / retirement / health-savings"
// scopes without needing to pick each individual account. `string` is a
// concrete account id like U12345678 (or numeric id stringified).
export type SelectedAccount = 'all' | 'taxable' | 'ira' | 'hsa' | string;

export interface BrokerAccount {
  id: number;
  account_number: string;
  account_name?: string;
  account_type?: string; // e.g., TAXABLE, IRA
  broker?: string; // IBKR, etc.
  is_enabled?: boolean;
}

/** Raw shape from GET /accounts (backend may use snake_case or camelCase). */
export interface BrokerAccountApiRow {
  id: number;
  account_number?: string;
  accountNumber?: string;
  account_id?: string;
  account_name?: string;
  accountName?: string;
  alias?: string;
  account_type?: string;
  type?: string;
  broker?: string;
  brokerage?: string;
  is_enabled?: boolean;
}

export interface AccountContextValue {
  accounts: BrokerAccount[];
  loading: boolean;
  error: string | null;
  selected: SelectedAccount;
  setSelected: (value: SelectedAccount) => void;
  refetch: () => void;
}

export const AccountContext = createContext<AccountContextValue | undefined>(undefined);

const STORAGE_KEY = 'qm.selectedAccount';
const URL_PARAM = 'account';

export const AccountProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [accounts, setAccounts] = useState<BrokerAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SelectedAccount>('all');
  const [refetchVersion, setRefetchVersion] = useState(0);
  const { isLoaded, isSignedIn } = useUser();

  // Bootstrap selected from URL or localStorage
  useEffect(() => {
    const url = new URL(window.location.href);
    const p = url.searchParams.get(URL_PARAM) as SelectedAccount | null;
    if (p && p.length > 0) {
      setSelected(p);
      localStorage.setItem(STORAGE_KEY, p);
    } else {
      const saved = (localStorage.getItem(STORAGE_KEY) as SelectedAccount | null) || 'all';
      setSelected(saved);
    }
  }, []);

  // Keep URL query param in sync
  useEffect(() => {
    const url = new URL(window.location.href);
    if (selected && selected !== 'all') {
      url.searchParams.set(URL_PARAM, selected);
    } else {
      url.searchParams.delete(URL_PARAM);
    }
    window.history.replaceState({}, '', url.toString());
    localStorage.setItem(STORAGE_KEY, selected);
  }, [selected]);

  // Load accounts list (only when authenticated with Clerk)
  useEffect(() => {
    const load = async () => {
      if (!isLoaded || !isSignedIn) {
        setAccounts([]);
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        // GET /api/v1/accounts
        const res = await api.get<BrokerAccountApiRow[]>('/accounts');
        const list: BrokerAccountApiRow[] = Array.isArray(res.data) ? res.data : [];
        // Normalize minimal fields we need
        const normalized: BrokerAccount[] = list
          .filter((a) => a.is_enabled !== false)
          .map((a) => ({
            id: a.id,
            account_number: a.account_number || a.accountNumber || a.account_id || '',
            account_name: a.account_name || a.accountName || a.alias || a.account_number || '',
            account_type: a.account_type || a.type || '',
            broker: a.broker || a.brokerage || 'IBKR',
            is_enabled: a.is_enabled !== undefined ? a.is_enabled : true,
          }));
        setAccounts(normalized);
      } catch (e: any) {
        const status = e?.status || e?.response?.status;
        if (status === 401 || status === 403) {
          setAccounts([]);
          setError(null);
        } else {
          setError(e?.message || 'Failed to load accounts');
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [isLoaded, isSignedIn, refetchVersion]);

  // Reset selection when the selected account is no longer in the enabled list
  useEffect(() => {
    if (
      !accounts.length ||
      selected === 'all' ||
      selected === 'taxable' ||
      selected === 'ira' ||
      selected === 'hsa'
    ) return;
    const exists = accounts.some(
      (a) => a.account_number === selected || String(a.id) === selected,
    );
    if (!exists) {
      setSelected('all');
    }
  }, [accounts, selected]);

  const refetch = useMemo(() => () => setRefetchVersion((v) => v + 1), []);

  const value = useMemo<AccountContextValue>(() => {
    return { accounts, loading, error, selected, setSelected, refetch };
  }, [accounts, loading, error, selected, refetch]);

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
};

export const useAccountContext = (): AccountContextValue => {
  const ctx = useContext(AccountContext);
  if (!ctx) throw new Error('useAccountContext must be used within AccountProvider');
  return ctx;
};

