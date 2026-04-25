import React from 'react';
import { DollarSign, Info, TrendingDown, TrendingUp } from 'lucide-react';
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";

import AppDivider from './AppDivider';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';
import { cn } from '@/lib/utils';

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

export interface AccountSelectorProps {
  accounts: AccountData[];
  selectedAccount: string;
  onAccountChange: (accountId: string) => void;
  showAllOption?: boolean;
  showSummary?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'simple' | 'detailed';
}

const AccountSelector: React.FC<AccountSelectorProps> = ({
  accounts = [],
  selectedAccount,
  onAccountChange,
  showAllOption = true,
  showSummary = true,
  variant = 'detailed',
}) => {
  const { currency } = useUserPreferences();

  const totalValue = accounts.reduce((sum, acc) => sum + acc.total_value, 0);
  const totalPnL = accounts.reduce((sum, acc) => sum + acc.unrealized_pnl, 0);
  const totalPnLPct = totalValue > 0 ? (totalPnL / (totalValue - totalPnL)) * 100 : 0;
  const totalPositions = accounts.reduce((sum, acc) => sum + acc.positions_count, 0);

  const formatCurrency = (amount: number) =>
    formatMoney(amount || 0, currency, { maximumFractionDigits: 0, minimumFractionDigits: 0 });

  const formatPercentage = (pct: number | undefined) => {
    if (pct === undefined || pct === null || Number.isNaN(pct)) return '0.00%';
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
  };

  const getChangeClass = (value: number | undefined) => {
    if (value === undefined || value === null || Number.isNaN(value)) return 'text-muted-foreground';
    return value >= 0 ? 'text-[rgb(var(--status-success))]' : 'text-[rgb(var(--status-danger))]';
  };

  const selectedAccountData = accounts.find((acc) => acc.account_id === selectedAccount);

  if (variant === 'simple') {
    return (
      <select
        value={selectedAccount}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onAccountChange(e.target.value)}
        disabled={!accounts.length}
        className="max-w-[250px] rounded-[10px] border border-input bg-background px-2.5 py-2 text-sm text-foreground shadow-xs dark:bg-input/30"
      >
        {showAllOption ? <option value="all">All Accounts ({accounts.length})</option> : null}
        {accounts.map((account) => (
          <option key={account.account_id} value={account.account_id}>
            {account.account_name} - {formatCurrency(account.total_value)}
          </option>
        ))}
      </select>
    );
  }

  return (
    <Card className="border-border">
      <CardContent className="flex flex-col gap-4 pt-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-foreground">Account</span>
            <Badge variant="secondary" className="font-medium">
              {accounts.length} linked
            </Badge>
          </div>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-auto gap-2 py-2 font-semibold shadow-xs"
              >
                <span>{selectedAccountData?.account_name || 'All Accounts'}</span>
                <Info className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              </Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={4}
                className={cn(
                  'z-50 max-h-[min(24rem,70vh)] min-w-[var(--radix-dropdown-menu-trigger-width)] overflow-y-auto rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md',
                  'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2'
                )}
              >
                {showAllOption ? (
                  <DropdownMenu.Item
                    className={cn(
                      'flex cursor-default flex-col gap-0 rounded-sm px-3 py-2 text-left text-sm outline-none',
                      'focus:bg-accent focus:text-accent-foreground'
                    )}
                    onSelect={() => onAccountChange('all')}
                  >
                    <span className="font-semibold">All Accounts</span>
                    <span className="text-xs text-muted-foreground">Combined portfolio view</span>
                  </DropdownMenu.Item>
                ) : null}
                {accounts.map((account) => (
                  <DropdownMenu.Item
                    key={account.account_id}
                    className={cn(
                      'cursor-default rounded-sm px-3 py-2 text-sm outline-none',
                      'focus:bg-accent focus:text-accent-foreground'
                    )}
                    onSelect={() => onAccountChange(account.account_id)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-semibold">{account.account_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {account.broker} • {account.account_type}
                        </div>
                      </div>
                      <span className="shrink-0 font-semibold">{formatCurrency(account.total_value)}</span>
                    </div>
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>

        {showSummary ? (
          <>
            <AppDivider />

            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatBlock label="Total Value" value={formatCurrency(totalValue)} />
              <StatBlock
                label="Total P&L"
                value={
                  <span className={cn('inline-flex items-center gap-1', getChangeClass(totalPnL))}>
                    {totalPnL >= 0 ? (
                      <TrendingUp className="size-3.5 shrink-0" aria-hidden />
                    ) : (
                      <TrendingDown className="size-3.5 shrink-0" aria-hidden />
                    )}
                    {formatCurrency(totalPnL)}
                  </span>
                }
                help={formatPercentage(totalPnLPct)}
              />
              <StatBlock label="Accounts" value={String(accounts.length)} />
              <StatBlock label="Total Positions" value={String(totalPositions)} />
            </div>

            {selectedAccountData && selectedAccount !== 'all' ? (
              <div>
                <p className="mb-2 text-sm font-semibold">Selected account</p>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <StatBlock label="Account Value" value={formatCurrency(selectedAccountData?.total_value || 0)} />
                  <StatBlock
                    label="Unrealized P&L"
                    value={
                      <span
                        className={cn(
                          'inline-flex items-center gap-1',
                          getChangeClass(selectedAccountData?.unrealized_pnl)
                        )}
                      >
                        {(selectedAccountData?.unrealized_pnl || 0) >= 0 ? (
                          <TrendingUp className="size-3.5 shrink-0" aria-hidden />
                        ) : (
                          <TrendingDown className="size-3.5 shrink-0" aria-hidden />
                        )}
                        {formatCurrency(selectedAccountData?.unrealized_pnl || 0)}
                      </span>
                    }
                    help={formatPercentage(selectedAccountData.unrealized_pnl_pct)}
                  />
                  <StatBlock label="Positions" value={String(selectedAccountData?.positions_count || 0)} />
                  <StatBlock
                    label="Allocation"
                    value={`${(selectedAccountData?.allocation_pct ?? 0).toFixed(1)}%`}
                  />
                </div>

                {selectedAccountData?.buying_power !== undefined ||
                selectedAccountData?.available_funds !== undefined ||
                selectedAccountData?.day_change !== undefined ? (
                  <div className="mt-4">
                    <AppDivider />
                    <div className="mt-4 flex flex-wrap gap-4">
                      {selectedAccountData?.buying_power !== undefined ? (
                        <div className="flex items-center gap-2 text-sm">
                          <DollarSign className="size-4 text-muted-foreground" aria-hidden />
                          <span className="text-muted-foreground">Buying Power:</span>
                          <span className="font-semibold">{formatCurrency(selectedAccountData.buying_power)}</span>
                        </div>
                      ) : null}
                      {selectedAccountData?.available_funds !== undefined ? (
                        <div className="flex items-center gap-2 text-sm">
                          <DollarSign className="size-4 text-muted-foreground" aria-hidden />
                          <span className="text-muted-foreground">Available:</span>
                          <span className="font-semibold">{formatCurrency(selectedAccountData.available_funds)}</span>
                        </div>
                      ) : null}
                      {selectedAccountData?.day_change !== undefined ? (
                        <div className="flex items-center gap-2 text-sm">
                          {selectedAccountData.day_change >= 0 ? (
                            <TrendingUp className={cn('size-4', getChangeClass(selectedAccountData.day_change))} />
                          ) : (
                            <TrendingDown className={cn('size-4', getChangeClass(selectedAccountData.day_change))} />
                          )}
                          <span className="text-muted-foreground">Day:</span>
                          <span
                            className={cn('font-semibold', getChangeClass(selectedAccountData.day_change))}
                          >
                            {formatCurrency(selectedAccountData.day_change)}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
};

function StatBlock({
  label,
  value,
  help,
}: {
  label: string;
  value: React.ReactNode;
  help?: string;
}) {
  return (
    <div className="grid gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="text-base font-medium text-foreground">{value}</div>
      {help ? <span className="text-xs text-muted-foreground">{help}</span> : null}
    </div>
  );
}

export default AccountSelector;
