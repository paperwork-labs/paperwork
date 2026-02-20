import React, { type ReactNode } from 'react';
import {
  Box,
  VStack,
  AlertRoot,
  AlertIndicator,
  AlertDescription,
  Spinner,
  Text,
} from '@chakra-ui/react';
import AccountSelector, { type AccountData } from './AccountSelector';
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
      <VStack gap={4} py={8}>
        <Spinner size="xl" color="brand.500" />
        <Text color="fg.muted">Loading account data…</Text>
      </VStack>
    );
  }

  if (error) {
    return (
      <AlertRoot status="error" borderRadius="lg" borderWidth="1px" borderColor="border.subtle" bg="bg.card">
        <AlertIndicator />
        <AlertDescription>Error loading account data: {error}</AlertDescription>
      </AlertRoot>
    );
  }

  return (
    <VStack gap={6} align="stretch">
      <AccountSelector
        accounts={accounts}
        selectedAccount={filterState.selectedAccount}
        onAccountChange={handleAccountChange}
        showAllOption={config.showAllOption}
        showSummary={config.showSummary}
        size={config.size}
        variant={config.variant}
      />

      <Box>{children(filterState.filteredData as T[], filterState)}</Box>
    </VStack>
  );
}

export default AccountFilterWrapper;


