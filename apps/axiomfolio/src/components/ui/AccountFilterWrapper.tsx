import React, { type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

import AccountSelector, { type AccountData } from './AccountSelector';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAccountFilter, type FilterableItem, type AccountFilterConfig } from '../../hooks/useAccountFilter';
import { useAccountContext } from '../../context/AccountContext';

interface AccountFilterWrapperProps<T extends FilterableItem> {
  data: T[];
  accounts: AccountData[];
  config?: AccountFilterConfig;
  loading?: boolean;
  error?: string | null;
  onAccountChange?: (accountId: string) => void;
  /** When loading is true, render this instead of the default Spinner (e.g. TableSkeleton). */
  loadingComponent?: ReactNode;
  children: (filteredData: T[], filterState: ReturnType<typeof useAccountFilter>) => ReactNode;
}

/**
 * Reusable wrapper component that provides consistent account filtering UI and logic.
 */
function AccountFilterWrapper<T extends FilterableItem>({
  data,
  accounts,
  config = {},
  loading = false,
  error = null,
  onAccountChange,
  loadingComponent,
  children,
}: AccountFilterWrapperProps<T>) {
  const filterState = useAccountFilter(data, accounts, config);
  const { setSelected: setContextSelected } = useAccountContext();

  const handleAccountChange = (accountId: string) => {
    filterState.setSelectedAccount(accountId);
    setContextSelected(accountId);
    onAccountChange?.(accountId);
  };

  if (loading) {
    if (loadingComponent) return <>{loadingComponent}</>;
    return (
      <div className="flex flex-col items-center gap-4 py-8">
        <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
        <p className="text-sm text-muted-foreground">Loading account data…</p>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className="rounded-lg border">
        <AlertDescription>Error loading account data: {error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-6 items-stretch">
      <AccountSelector
        accounts={accounts}
        selectedAccount={filterState.selectedAccount}
        onAccountChange={handleAccountChange}
        showAllOption={config.showAllOption}
        showSummary={config.showSummary}
        size={config.size}
        variant={config.variant}
      />

      <div>{children(filterState.filteredData as T[], filterState)}</div>
    </div>
  );
}

export default AccountFilterWrapper;
