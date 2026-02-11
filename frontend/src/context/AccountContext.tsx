import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import api from '../services/api';
import { useAuth } from './AuthContext';

export type SelectedAccount = 'all' | 'taxable' | 'ira' | string; // string = concrete account id like U12345678

export interface BrokerAccount {
  id: number;
  account_number: string;
  account_name?: string;
  account_type?: string; // e.g., TAXABLE, IRA
  broker?: string; // IBKR, etc.
  is_enabled?: boolean;
}

export interface AccountContextValue {
  accounts: BrokerAccount[];
  loading: boolean;
  error: string | null;
  selected: SelectedAccount;
  setSelected: (value: SelectedAccount) => void;
}

export const AccountContext = createContext<AccountContextValue | undefined>(undefined);

const STORAGE_KEY = 'qm.selectedAccount';
const URL_PARAM = 'account';

export const AccountProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [accounts, setAccounts] = useState<BrokerAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SelectedAccount>('all');
  const { token, ready, logout } = useAuth();

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

  // Load accounts list (only when authenticated)
  useEffect(() => {
    const load = async () => {
      if (!ready || !token) {
        setAccounts([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        // GET /api/v1/accounts
        const res = await api.get('/accounts');
        const list: any[] = res.data || [];
        // Normalize minimal fields we need
        const normalized: BrokerAccount[] = list.map((a: any) => ({
          id: a.id,
          account_number: a.account_number || a.accountNumber || a.account_id || '',
          account_name: a.account_name || a.accountName || a.alias || a.account_number || '',
          account_type: a.account_type || a.type || '',
          broker: a.broker || a.brokerage || 'IBKR',
          is_enabled: a.is_enabled !== undefined ? a.is_enabled : true,
        }));
        setAccounts(normalized);
      } catch (e: any) {
        setError(e?.message || 'Failed to load accounts');
        // If unauthorized, clear accounts
        if (e?.status === 401 || e?.response?.status === 401) {
          setAccounts([]);
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token, ready]);

  const value = useMemo<AccountContextValue>(() => {
    return { accounts, loading, error, selected, setSelected };
  }, [accounts, loading, error, selected]);

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
};

export const useAccountContext = (): AccountContextValue => {
  const ctx = useContext(AccountContext);
  if (!ctx) throw new Error('useAccountContext must be used within AccountProvider');
  return ctx;
};


